#!/usr/bin/env python3
"""OWON XDM1000 / XDM1000 用の上位制御クラスである。

このファイルは「測定器としての使いやすい API」を提供する上位層である。
SCPI コマンドを直接並べる層ではない。SCPI の低レベル API は
xdm1000_scpi.py に集約する。

設計方針
--------

* Python threading は使わない。
* ``remote()`` / ``local()`` は上位 API として公開しない。
* multiprocessing.Process で測定ワーカーを分離する。
* 測定ワーカープロセスだけがシリアルポートを保持する。
* 親プロセスはサーバー側 API 状態、結果、開始・停止要求を管理する。
* 長時間測定中は ``running=True`` とし、別の測定・設定 API は拒否する。
* ``get_state()``, ``stop_job()``, ``get_continuous_result()``,
  ``get_statistics_result()`` は測定中でも呼べる。

実装する測定モード
------------------

1. 1 shot 測定
    ``meas_one_shot()`` / ``meas()`` で 1 回だけ ``MEAS1?`` を読む。

2. 連続測定モード
    ``start_continuous_meas(duration=..., interval=0.0)`` で、指定時間だけ
    ワーカープロセスが最速または指定周期で ``MEAS1?`` を読み、各点に
    PC 側時刻を付与して保存する。結果は測定終了後にまとめて
    ``get_continuous_result()`` で取得する。

3. 統計モード（テスト用）
    ``CALCulate:FUNCtion AVERage`` と ``CALCulate:AVERage:ALL?`` を使う実験用
    ラッパである。XDM1000 の statistics 開始・クリア条件がマニュアルだけでは
    確定できないため、現段階では時間窓平均の正式 API とは扱わない。
"""

from __future__ import annotations

import math
import multiprocessing as mp
import queue
import time
import traceback
import uuid
from dataclasses import dataclass
from typing import Any, Literal, Optional

try:
    from .xdm1000_scpi import Xdm1000Scpi
except ImportError:  # 直接実行時のサンプル用である。
    from xdm1000_scpi import Xdm1000Scpi


MeasureKind = Literal[
    "voltage_dc",
    "voltage_ac",
    "current_dc",
    "current_ac",
    "resistance",
    "fresistance",
    "frequency",
    "period",
    "capacitance",
    "temperature_rtd",
    "diode",
    "continuity",
]


class DeviceBusyError(RuntimeError):
    """測定器が長時間測定中のため、測定・設定要求を拒否したことを表す。"""


class DeviceWorkerError(RuntimeError):
    """測定ワーカープロセス側で例外が発生したことを表す。"""


@dataclass(frozen=True)
class MeasurementConfig:
    """現在の測定条件を表す小さなデータ構造である。"""

    kind: MeasureKind
    range_value: str | int | float = "AUTO"
    rate: str = "F"


def _sample_clock(t0_perf: float) -> dict[str, float]:
    """ホスト PC 側の時刻情報を作る。

    ``time.time()`` は UNIX 時刻であり、ログとの対応に使う。
    ``time.perf_counter()`` は単調増加時計であり、相対時間・経過時間に使う。
    """
    perf = time.perf_counter()
    return {
        "host_time": time.time(),
        "host_perf": perf,
        "t_rel": perf - t0_perf,
    }


def _configure_meas(
    scpi: Xdm1000Scpi,
    kind: str,
    range_value: str | int | float = "AUTO",
) -> None:
    """上位の測定種別名を SCPI の CONFigure 系コマンドへ写像する。"""
    if kind == "voltage_dc":
        scpi.configure_voltage_dc(range_value)
    elif kind == "voltage_ac":
        scpi.configure_voltage_ac(range_value)
    elif kind == "current_dc":
        scpi.configure_current_dc(range_value)
    elif kind == "current_ac":
        scpi.configure_current_ac(range_value)
    elif kind == "resistance":
        scpi.configure_resistance(range_value)
    elif kind == "fresistance":
        scpi.configure_fresistance(range_value)
    elif kind == "frequency":
        scpi.configure_frequency()
    elif kind == "period":
        scpi.configure_period()
    elif kind == "capacitance":
        scpi.configure_capacitance(range_value)
    elif kind == "temperature_rtd":
        scpi.configure_temperature_rtd()
    elif kind == "diode":
        scpi.configure_diode()
    elif kind == "continuity":
        scpi.configure_continuity()
    else:
        raise ValueError(f"未対応の測定種別である: {kind!r}")


def _calc_stats(values: list[float]) -> dict[str, float | int | None]:
    """サーバー側で取得した測定値リストから基本統計を計算する。"""
    if not values:
        return {
            "count": 0,
            "minimum": None,
            "maximum": None,
            "average": None,
            "stdev_population": None,
        }
    count = len(values)
    average = sum(values) / count
    variance = sum((x - average) ** 2 for x in values) / count
    return {
        "count": count,
        "minimum": min(values),
        "maximum": max(values),
        "average": average,
        "stdev_population": math.sqrt(variance),
    }


def _worker_loop(
    command_q: mp.Queue,
    response_q: mp.Queue,
    state: Any,
    result_store: Any,
    stop_event: mp.Event,
    port: str,
    timeout: float,
    baudrate: int,
    logger_name: Optional[str] = None,
) -> None:
    """測定ワーカープロセスの本体である。

    この関数だけが `Xdm1000Scpi`` を生成し、シリアルポートを保持する。
    親プロセスはシリアルポートへ直接触らない。
    """
    scpi: Xdm1000Scpi | None = None

    def set_idle(message: str = "idle") -> None:
        """共有 state を idle に戻す。"""
        state["running"] = False
        state["job_id"] = None
        state["job_type"] = None
        state["started_at"] = None
        state["finished_at"] = None
        state["error"] = None
        state["traceback"] = None
        state["message"] = message

    def set_running(job_id: str, job_type: str, args: dict[str, Any]) -> None:
        """共有 state を running にする。"""
        state["running"] = True
        state["job_id"] = job_id
        state["job_type"] = job_type
        state["started_at"] = time.time()
        state["finished_at"] = None
        state["error"] = None
        state["traceback"] = None
        state["message"] = "running"
        state["meas_kind"] = args.get("kind")
        state["range_value"] = args.get("range_value", "AUTO")
        state["rate"] = args.get("rate", "F")
        state["duration"] = args.get("duration")
        state["interval"] = args.get("interval")
        state["sample_count"] = 0
        state["last_value"] = None
        state["last_host_time"] = None

    def finish(message: str = "finished") -> None:
        """共有 state を終了状態にする。"""
        state["running"] = False
        state["finished_at"] = time.time()
        state["message"] = message

    def fail(exc: BaseException) -> None:
        """共有 state にワーカー例外を記録する。"""
        state["running"] = False
        state["finished_at"] = time.time()
        state["error"] = "".join(
            traceback.format_exception_only(type(exc), exc)
        ).strip()
        state["traceback"] = traceback.format_exc()
        state["message"] = "error"

    try:
        scpi = Xdm1000Scpi(
            port=port,
            timeout=timeout,
            baudrate=baudrate,
        )
        # 上位制御クラスでは remote/local を公開しない。
        # 通信モード制御はワーカー起動・終了時の内部処理として扱う。
        scpi.remote()

        state["worker_alive"] = True
        state["port"] = port
        state["baudrate"] = baudrate
        set_idle("worker_ready")

    except BaseException as exc:
        state["worker_alive"] = False
        state["error"] = repr(exc)
        state["traceback"] = traceback.format_exc()
        return

    while True:
        try:
            command = command_q.get()
            req_id = command.get("req_id")
            name = command.get("cmd")
            args = command.get("args", {})

            try:
                if name == "shutdown":
                    response_q.put({"req_id": req_id, "ok": True, "result": None})
                    break

                if name == "idn":
                    response_q.put({"req_id": req_id, "ok": True, "result": scpi.idn()})

                elif name == "reset":
                    scpi.reset()
                    response_q.put({"req_id": req_id, "ok": True, "result": None})

                elif name == "set_meas_mode":
                    _configure_meas(scpi, args["kind"], args.get("range_value", "AUTO"))
                    scpi.set_rate(args.get("rate", "F"))
                    state["meas_kind"] = args["kind"]
                    state["range_value"] = args.get("range_value", "AUTO")
                    state["rate"] = args.get("rate", "F")
                    response_q.put({"req_id": req_id, "ok": True, "result": dict(args)})

                elif name == "one_shot":
                    _configure_meas(scpi, args["kind"], args.get("range_value", "AUTO"))
                    scpi.set_rate(args.get("rate", "F"))
                    time.sleep(float(args.get("settle", 0.0)))
                    t0 = time.perf_counter()
                    before = _sample_clock(t0)
                    value = scpi.meas_main()
                    after = _sample_clock(t0)
                    result = {
                        "kind": args["kind"],
                        "range_value": args.get("range_value", "AUTO"),
                        "rate": args.get("rate", "F"),
                        "value": value,
                        "host_time_start": before["host_time"],
                        "host_time_end": after["host_time"],
                        "read_elapsed": after["host_perf"] - before["host_perf"],
                    }
                    response_q.put({"req_id": req_id, "ok": True, "result": result})

                elif name == "start_continuous":
                    job_id = args["job_id"]
                    duration = float(args["duration"])
                    interval = float(args.get("interval", 0.0))
                    if duration <= 0:
                        raise ValueError("duration は正の値でなければならない。")
                    if interval < 0:
                        raise ValueError("interval は 0 以上でなければならない。")

                    set_running(job_id, "continuous", args)
                    stop_event.clear()
                    _configure_meas(scpi, args["kind"], args.get("range_value", "AUTO"))
                    scpi.set_rate(args.get("rate", "F"))
                    time.sleep(float(args.get("settle", 0.0)))
                    response_q.put(
                        {"req_id": req_id, "ok": True, "result": {"job_id": job_id}}
                    )

                    samples: list[dict[str, Any]] = []
                    t0 = time.perf_counter()
                    deadline = t0 + duration
                    index = 0
                    try:
                        while (
                            time.perf_counter() < deadline and not stop_event.is_set()
                        ):
                            s0 = _sample_clock(t0)
                            value = scpi.meas_main()
                            s1 = _sample_clock(t0)
                            sample = {
                                "index": index,
                                "kind": args["kind"],
                                "value": value,
                                "host_time_start": s0["host_time"],
                                "host_time_end": s1["host_time"],
                                "t_rel_start": s0["t_rel"],
                                "t_rel_end": s1["t_rel"],
                                "read_elapsed": s1["host_perf"] - s0["host_perf"],
                            }
                            samples.append(sample)
                            index += 1
                            state["sample_count"] = index
                            state["last_value"] = value
                            state["last_host_time"] = s1["host_time"]

                            if interval > 0:
                                # interval は「読み取り完了後から次回開始までの待ち時間」である。
                                # interval=0 の場合は Python 側では待たず、装置と通信が許す限り最速で読む。
                                sleep_until = time.perf_counter() + interval
                                while time.perf_counter() < sleep_until:
                                    if stop_event.is_set():
                                        break
                                    time.sleep(
                                        min(0.005, sleep_until - time.perf_counter())
                                    )

                    except BaseException as exc:
                        result_store["continuous"] = {
                            "job_id": job_id,
                            "ok": False,
                            "error": repr(exc),
                            "traceback": traceback.format_exc(),
                            "samples": samples,
                        }
                        fail(exc)
                    else:
                        values = [float(s["value"]) for s in samples]
                        result_store["continuous"] = {
                            "job_id": job_id,
                            "ok": True,
                            "stopped": stop_event.is_set(),
                            "kind": args["kind"],
                            "range_value": args.get("range_value", "AUTO"),
                            "rate": args.get("rate", "F"),
                            "duration_requested": duration,
                            "interval_requested": interval,
                            "settle": float(args.get("settle", 0.0)),
                            "samples": samples,
                            "stats": _calc_stats(values),
                            "started_at": state.get("started_at"),
                            "finished_at": time.time(),
                        }
                        finish("stopped" if stop_event.is_set() else "finished")

                elif name == "start_statistics":
                    job_id = args["job_id"]
                    duration = float(args["duration"])
                    if duration <= 0:
                        raise ValueError("duration は正の値でなければならない。")

                    set_running(job_id, "statistics", args)
                    stop_event.clear()
                    _configure_meas(scpi, args["kind"], args.get("range_value", "AUTO"))
                    scpi.set_rate(args.get("rate", "F"))
                    time.sleep(float(args.get("settle", 0.0)))
                    response_q.put(
                        {"req_id": req_id, "ok": True, "result": {"job_id": job_id}}
                    )

                    try:
                        # 統計モードは現段階ではテスト用である。
                        # XDM1000 の statistics がいつ clear/start されるかは実機確認が必要である。
                        # したがって、ここでは CALC:FUNC AVERage を設定して duration 秒待ち、
                        # CALC:AVERage:ALL? を読むだけに留める。

                        scpi.set_calc_function("AVERage")
                        t0 = time.perf_counter()
                        deadline = t0 + duration
                        while (
                            time.perf_counter() < deadline and not stop_event.is_set()
                        ):
                            time.sleep(min(0.05, deadline - time.perf_counter()))
                        stats = scpi.get_average_all()
                        result_store["statistics"] = {
                            "job_id": job_id,
                            "ok": True,
                            "stopped": stop_event.is_set(),
                            "kind": args["kind"],
                            "range_value": args.get("range_value", "AUTO"),
                            "rate": args.get("rate", "F"),
                            "duration_requested": duration,
                            "stats": {
                                "minimum": stats.minimum,
                                "maximum": stats.maximum,
                                "average": stats.average,
                                "count": stats.count,
                            },
                            "note": (
                                "CALCulate:AVERage:ALL? を使った statistics テスト結果である。"
                                "statistics の clear/start 条件が未確認のため、"
                                "この値を duration 秒の厳密な平均とは扱わない。"
                            ),
                            "started_at": state.get("started_at"),
                            "finished_at": time.time(),
                        }
                        finish("stopped" if stop_event.is_set() else "finished")
                    except BaseException as exc:
                        result_store["statistics"] = {
                            "job_id": job_id,
                            "ok": False,
                            "error": repr(exc),
                            "traceback": traceback.format_exc(),
                        }
                        fail(exc)

                else:
                    raise ValueError(f"未知の worker command である: {name!r}")

            except BaseException as exc:
                response_q.put(
                    {
                        "req_id": req_id,
                        "ok": False,
                        "error": repr(exc),
                        "traceback": traceback.format_exc(),
                    }
                )
        except BaseException:
            state["worker_loop_error"] = traceback.format_exc()

    try:
        if scpi is not None:
            try:
                scpi.local()
            except Exception:
                pass
            scpi.close()
    finally:
        state["worker_alive"] = False


class Xdm1000Ctrl:
    """XDM1000/XDM1000 を測定器として扱う上位制御クラスである。

    コンストラクタで測定ワーカープロセスを起動する。ワーカープロセスは起動から
    ``close()`` までシリアルポートを保持する。親プロセスはサーバー API として
    呼び出される想定であり、長時間測定中でも状態取得と結果取得だけは応答できる。
    """

    def __init__(
        self,
        port: str,
        timeout: float = 2.0,
        baudrate: int = 115200,
    ) -> None:
        """XDM1000 上位制御クラスを生成し、測定ワーカーを起動する。"""
        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate

        self._manager = mp.Manager()
        self._state = self._manager.dict()
        self._result_store = self._manager.dict()
        self._command_q: mp.Queue = mp.Queue()
        self._response_q: mp.Queue = mp.Queue()
        self._stop_event = mp.Event()
        self._rpc_lock = mp.Lock()

        self._process = mp.Process(
            target=_worker_loop,
            kwargs={
                "command_q": self._command_q,
                "response_q": self._response_q,
                "state": self._state,
                "result_store": self._result_store,
                "stop_event": self._stop_event,
                "port": port,
                "timeout": timeout,
                "baudrate": baudrate,
            },
            daemon=True,
        )
        self._process.start()

    # ------------------------------------------------------------------
    # 内部 RPC
    # ------------------------------------------------------------------

    def _is_running(self) -> bool:
        """長時間測定中かどうかを返す。"""
        return bool(self._state.get("running", False))

    def _require_not_running(self) -> None:
        """測定中なら測定・設定 API を拒否する。"""
        if self._is_running():
            raise DeviceBusyError(
                f"測定器は running 中である: "
                f"job_type={self._state.get('job_type')}, job_id={self._state.get('job_id')}"
            )

    def _rpc(
        self,
        name: str,
        args: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """
        親プロセスから測定ワーカーへ 1 コマンドを送る。
        """
        req_id = uuid.uuid4().hex
        with self._rpc_lock:
            self._command_q.put({"req_id": req_id, "cmd": name, "args": args or {}})
            deadline = None if timeout is None else time.time() + timeout
            while True:
                remaining = (
                    None if deadline is None else max(0.0, deadline - time.time())
                )
                if deadline is not None and remaining <= 0:
                    raise TimeoutError(f"worker 応答待ち timeout: {name!r}")
                try:
                    response = self._response_q.get(timeout=remaining)
                except queue.Empty as exc:
                    raise TimeoutError(f"worker 応答待ち timeout: {name!r}") from exc
                if response.get("req_id") != req_id:
                    raise RuntimeError(
                        f"worker response の req_id が一致しない: {response!r}"
                    )
                if response.get("ok"):
                    return response.get("result")
                raise DeviceWorkerError(
                    f"{response.get('error')}\n{response.get('traceback', '')}"
                )

    # ------------------------------------------------------------------
    # ライフサイクル
    # ------------------------------------------------------------------

    def close(self) -> None:
        """測定ワーカープロセスを終了する。"""
        if self._process.is_alive():
            try:
                self._rpc("shutdown", timeout=2.0)
            except Exception:
                pass
            self._process.join(timeout=2.0)
            if self._process.is_alive():
                self._process.terminate()
                self._process.join(timeout=2.0)
        self._manager.shutdown()

    def disconnect(self) -> None:
        """サーバー停止時に呼ばれる解放用エイリアスである。"""
        self.close()

    def __enter__(self) -> "Xdm1000Ctrl":
        """with 文用のエントリである。"""
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """with 文終了時にワーカーを停止する。"""
        self.close()

    # ------------------------------------------------------------------
    # 測定中でも許可する API
    # ------------------------------------------------------------------

    def get_state(self) -> dict[str, Any]:
        """現在の状態を返す。測定中でも呼べる。"""
        state = dict(self._state)
        state["process_alive"] = self._process.is_alive()
        return state

    def is_running(self) -> bool:
        """長時間測定中なら True を返す。"""
        return self._is_running()

    def stop_job(self) -> dict[str, Any]:
        """実行中の長時間測定に停止要求を出す。測定中でも呼べる。"""
        self._stop_event.set()
        return self.get_state()

    def get_continuous_result(self, clear: bool = False) -> Optional[dict[str, Any]]:
        """連続測定の結果を返す。測定終了後にまとめて取得する想定である。"""
        result = self._result_store.get("continuous")
        if clear and "continuous" in self._result_store:
            del self._result_store["continuous"]
        return result

    def get_statistics_result(self, clear: bool = False) -> Optional[dict[str, Any]]:
        """統計モードテストの結果を返す。"""
        result = self._result_store.get("statistics")
        if clear and "statistics" in self._result_store:
            del self._result_store["statistics"]
        return result

    # ------------------------------------------------------------------
    # 測定中は拒否する通常 API
    # remote/local は公開しない。通信モード制御はワーカー内部で完結させる。
    # ------------------------------------------------------------------

    def idn(self) -> str:
        """*IDN? を返す。測定中は拒否する。"""
        self._require_not_running()
        return self._rpc("idn", timeout=5.0)

    def _reset_scpi_internal(self) -> None:
        """内部確認用に *RST を実行する。

        上位公開 API としては扱わない。通常の利用では呼ばない。
        測定中は拒否する。
        """
        self._require_not_running()
        self._rpc("reset", timeout=10.0)

    def set_meas_mode(
        self,
        kind: MeasureKind,
        range_value: str | int | float = "AUTO",
        rate: str = "F",
    ) -> dict[str, Any]:
        """測定種別・レンジ・速度を設定する。測定中は拒否する。"""
        self._require_not_running()
        return self._rpc(
            "set_meas_mode",
            {"kind": kind, "range_value": range_value, "rate": rate},
            timeout=10.0,
        )

    def meas_one_shot(
        self,
        kind: MeasureKind,
        range_value: str | int | float = "AUTO",
        rate: str = "F",
        settle: float = 0.0,
    ) -> dict[str, Any]:
        """1 shot 測定を実行する。

        ``kind`` と ``range_value`` と ``rate`` を設定し、必要なら ``settle`` 秒待ってから
        ``MEAS1?`` を 1 回読む。測定中は拒否する。
        """
        self._require_not_running()
        return self._rpc(
            "one_shot",
            {"kind": kind, "range_value": range_value, "rate": rate, "settle": settle},
            timeout=10.0 + max(0.0, settle),
        )

    def meas(
        self,
        kind: MeasureKind = "voltage_dc",
        range_value: str | int | float = "AUTO",
        rate: str = "F",
        settle: float = 0.0,
    ) -> dict[str, Any]:
        """1 shot 測定の短縮名である。"""
        return self.meas_one_shot(
            kind=kind,
            range_value=range_value,
            rate=rate,
            settle=settle,
        )

    def meas_voltage_dc(
        self, range_value: str | int | float = "AUTO", rate: str = "F"
    ) -> dict[str, Any]:
        """DC 電圧を 1 shot 測定する。"""
        return self.meas_one_shot("voltage_dc", range_value, rate)

    def meas_current_dc(
        self, range_value: str | int | float = "AUTO", rate: str = "F"
    ) -> dict[str, Any]:
        """DC 電流を 1 shot 測定する。"""
        return self.meas_one_shot("current_dc", range_value, rate)

    # ------------------------------------------------------------------
    # 長時間測定 API
    # ------------------------------------------------------------------

    def start_continuous_meas(
        self,
        kind: MeasureKind,
        duration: float,
        range_value: str | int | float = "AUTO",
        rate: str = "F",
        interval: float = 0.0,
        settle: float = 0.0,
    ) -> dict[str, Any]:
        """擬似 continuous 測定を開始する。

        ``duration`` 秒だけ、ワーカープロセス側で ``MEAS1?`` を繰り返す。
        ``interval=0`` の場合は Python 側では待たず、装置とシリアル通信が許す範囲で
        最速に読む。各サンプルには host 側の時刻を付与する。

        このメソッドはワーカーが job を受理した時点で戻る。結果は終了後に
        ``get_continuous_result()`` で取得する。
        """
        self._require_not_running()
        job_id = uuid.uuid4().hex
        return self._rpc(
            "start_continuous",
            {
                "job_id": job_id,
                "kind": kind,
                "duration": duration,
                "range_value": range_value,
                "rate": rate,
                "interval": interval,
                "settle": settle,
            },
            timeout=10.0 + max(0.0, settle),
        )

    def start_statistics_mode(
        self,
        kind: MeasureKind,
        duration: float,
        range_value: str | int | float = "AUTO",
        rate: str = "F",
        settle: float = 0.0,
    ) -> dict[str, Any]:
        """statistics モードのテスト測定を開始する。

        XDM1000 の ``CALCulate:AVERage:ALL?`` は minimum, maximum, average, count を
        返す統計機能である。ただし statistics の clear/start 条件が未確認なので、
        現段階では duration 秒の厳密な平均値 API ではなく、テスト機能として扱う。
        """
        self._require_not_running()
        job_id = uuid.uuid4().hex
        return self._rpc(
            "start_statistics",
            {
                "job_id": job_id,
                "kind": kind,
                "duration": duration,
                "range_value": range_value,
                "rate": rate,
                "settle": settle,
            },
            timeout=10.0 + max(0.0, settle),
        )

    def wait_until_done(
        self, dmm: Xdm1000Ctrl, poll_interval: float = 0.2
    ) -> dict[str, Any]:
        """running が終わるまで状態を表示しながら待つ。"""
        while True:
            state = self.get_state()
            print("STATE:", state)
            if not state.get("running", False):
                return state
            time.sleep(poll_interval)


# --------------------------------------
# テスト用の Function
# --------------------------------------


def _example_main() -> None:
    """上位制御クラスの動作確認用サンプルである。

    実行例::

        python xdm1000_ctrl.py /dev/cu.usbserial-140 --mode voltage_dc --duration 5

    1 shot 測定、擬似 continuous 測定、statistics テストを順に実行する。
    """
    # ----------------------------------------------------------------------
    # 接続設定
    # ----------------------------------------------------------------------

    PORT = "/dev/cu.usbserial-140"
    BAUDRATE = 115200
    TIMEOUT = 2.0

    # ----------------------------------------------------------------------
    # 測定条件
    # ----------------------------------------------------------------------

    MODE = "voltage_dc"

    # MODE = "voltage_ac"
    # MODE = "current_dc"
    # MODE = "current_ac"
    # MODE = "resistance"
    # MODE = "fresistance"
    # MODE = "frequency"
    # MODE = "period"
    # MODE = "capacitance"
    # MODE = "temperature_rtd"
    # MODE = "diode"
    # MODE = "continuity"

    RANGE = "AUTO"

    # RANGE = 10
    # RANGE = 100
    # RANGE = 1000

    RATE = "F"
    # RATE = "M"
    # RATE = "S"

    SETTLE = 0.2
    DURATION = 5.0
    INTERVAL = 0.0

    dmm = Xdm1000Ctrl(
        port=PORT,
        timeout=TIMEOUT,
        baudrate=BAUDRATE,
    )

    print("初期 state:", dmm.get_state())
    print("IDN:", dmm.idn())

    for i in range(10):
        print("1 shot:")
        print(
            dmm.meas_one_shot(
                kind=MODE,
                range_value=RANGE,
                rate=RATE,
                settle=SETTLE,
            )
        )

    # print("continuous start:")
    # print(
    #     dmm.start_continuous_meas(
    #         kind=MODE,
    #         duration=DURATION,
    #         range_value=RANGE,
    #         rate=RATE,
    #         interval=INTERVAL,
    #         settle=SETTLE,
    #     )
    # )

    dmm.wait_until_done(dmm)

    # result = dmm.get_continuous_result(clear=True)
    # print(result)
    # print("statistics start:")
    # print(
    #     dmm.start_statistics_mode(
    #         kind=MODE,
    #         duration=DURATION,
    #         range_value=RANGE,
    #         rate=RATE,
    #         settle=SETTLE,
    #     )
    # )

    # dmm.until_done(dmm)
    print(dmm.get_statistics_result(clear=True))


if __name__ == "__main__":
    _example_main()
