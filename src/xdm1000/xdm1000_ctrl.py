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

import multiprocessing as mp
import queue
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal

from xdm1000.xdm1000_worker import _Xdm1000Worker
from xdm1000.xdm1000_scpi import Xdm1000Scpi

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
    """測定ワーカープロセスの entry point である。

    multiprocessing.Process の target は pickle 可能な top-level 関数にしておく。
    実処理は ``_Xdm1000Worker`` に委譲する。
    """
    worker = _Xdm1000Worker(
        command_q=command_q,
        response_q=response_q,
        state=state,
        result_store=result_store,
        stop_event=stop_event,
        port=port,
        timeout=timeout,
        baudrate=baudrate,
        logger_name=logger_name,
    )
    worker.run()


class DeviceBusyError(RuntimeError):
    """測定器が長時間測定中のため、測定・設定要求を拒否したことを表す。"""


class DeviceWorkerError(RuntimeError):
    """測定ワーカープロセス側で例外が発生したことを表す。"""


@dataclass(frozen=True)
class MeasurementConfig:
    """現在の測定条件を表す小さなデータ構造である。"""

    kind: MeasureKind
    range_value: Union[str, int, float] = "AUTO"
    rate: str = "F"


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
        logger: Optional[Any] = None,
        log_level: Optional[str] = None,
        config: Any = None,
        use_process: bool = True,
    ) -> None:
        """
        XDM1000 上位制御クラスを生成し、測定ワーカーを起動
        """
        self.logger = logger
        self.log_level = log_level
        self.config = config
        self.use_process = use_process

        if config is not None:
            port = getattr(config, "PORT", port)
            timeout = getattr(config, "TIMEOUT", timeout)
            baudrate = getattr(config, "BAUDRATE", baudrate)

        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate

        self._current_meas_config = None
        self._direct_state = {
            "worker_alive": False,
            "port": self.port,
            "baudrate": self.baudrate,
            "running": False,
            "job_id": None,
            "job_type": None,
            "started_at": None,
            "finished_at": None,
            "error": None,
            "traceback": None,
            "message": "direct_scpi_mode",
        }
        self._direct_result_store = {
            "continuous": None,
            "statistics": None,
        }
        self._direct_stop_requested = False
        self.scpi = None  # type: Optional[Xdm1000Scpi]

        self._manager = None
        self._state = None
        self._result_store = None
        self._command_q = None
        self._response_q = None
        self._stop_event = None
        self._rpc_lock = None
        self._process = None

        if self.use_process:
            self._manager = mp.Manager()
            self._state = self._manager.dict()
            self._result_store = self._manager.dict()
            self._command_q = mp.Queue()  # type: mp.Queue
            self._response_q = mp.Queue()  # type: mp.Queue
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
        else:
            self.scpi = Xdm1000Scpi(
                port=port,
                timeout=timeout,
                baudrate=baudrate,
            )
            self.scpi.remote()

    # ------------------------------------------------------------------
    # 内部 RPC
    # ------------------------------------------------------------------

    def _is_running(self) -> bool:
        """
        長時間測定中かどうかを返す。
        """
        if self.use_process:
            return bool(self._state.get("running", False))
        return bool(self._direct_state.get("running", False))

    def _require_not_running(self) -> None:
        """
        測定中なら測定・設定 API を拒否
        """
        if self._is_running():
            if self.use_process:
                job_type = self._state.get("job_type")
                job_id = self._state.get("job_id")
            else:
                job_type = self._direct_state.get("job_type")
                job_id = self._direct_state.get("job_id")

            raise DeviceBusyError(
                f"測定器は running 中である: "
                f"job_type={job_type}, job_id={job_id}"
            )


    def _is_same_meas_config(
        self,
        kind: MeasureKind,
        range_value: Union[str, int, float] = "AUTO",
        rate: str = "F",
    ) -> bool:
        current = self._current_meas_config
        if current is None:
            return False
        if current.kind != kind:
            return False
        if current.range_value != range_value:
            return False
        if current.rate != rate:
            return False
        return True

    def _configure_meas_direct(
        self,
        kind: MeasureKind,
        range_value: Union[str, int, float] = "AUTO",
        rate: str = "F",
    ) -> None:
        if self._is_same_meas_config(kind, range_value, rate):
            return

        if kind == "voltage_dc":
            self.scpi.configure_voltage_dc(range_value)
        elif kind == "voltage_ac":
            self.scpi.configure_voltage_ac(range_value)
        elif kind == "current_dc":
            self.scpi.configure_current_dc(range_value)
        elif kind == "current_ac":
            self.scpi.configure_current_ac(range_value)
        elif kind == "resistance":
            self.scpi.configure_resistance(range_value)
        elif kind == "fresistance":
            self.scpi.configure_fresistance(range_value)
        elif kind == "frequency":
            self.scpi.configure_frequency()
        elif kind == "period":
            self.scpi.configure_period()
        elif kind == "capacitance":
            self.scpi.configure_capacitance(range_value)
        elif kind == "temperature_rtd":
            self.scpi.configure_temperature_rtd()
        elif kind == "diode":
            self.scpi.configure_diode()
        elif kind == "continuity":
            self.scpi.configure_continuity()
        else:
            raise ValueError("unsupported kind: {}".format(kind))

        self.scpi.set_rate(rate)
        self._current_meas_config = MeasurementConfig(
            kind=kind,
            range_value=range_value,
            rate=rate,
        )

    def _direct_begin_job(
        self,
        job_id: str,
        job_type: str,
    ) -> None:
        self._direct_state["running"] = True
        self._direct_state["job_id"] = job_id
        self._direct_state["job_type"] = job_type
        self._direct_state["started_at"] = time.time()
        self._direct_state["finished_at"] = None
        self._direct_state["error"] = None
        self._direct_state["traceback"] = None
        self._direct_stop_requested = False

    def _direct_finish_job(self) -> None:
        self._direct_state["running"] = False
        self._direct_state["job_id"] = None
        self._direct_state["job_type"] = None
        self._direct_state["finished_at"] = time.time()
        self._direct_stop_requested = False

    def _rpc(
        self,
        name: str,
        args: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """
        親プロセスから測定ワーカーへ 1 コマンドを送る。
        """
        if not self.use_process:
            raise RuntimeError("use_process=False では _rpc は使わない。")

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
        """
        測定ワーカープロセスを終了
        """
        if self.use_process:
            if self._process is not None and self._process.is_alive():
                try:
                    self._rpc("shutdown", timeout=2.0)
                except Exception:
                    pass
                self._process.join(timeout=2.0)
                if self._process.is_alive():
                    self._process.terminate()
                    self._process.join(timeout=2.0)

            if self._manager is not None:
                try:
                    self._manager.shutdown()
                except Exception:
                    pass
        else:
            if self.scpi is not None:
                try:
                    self.scpi.local()
                except Exception:
                    pass
                try:
                    self.scpi.close()
                except Exception:
                    pass
                self.scpi = None

    def disconnect(self) -> None:
        """サーバー停止時に呼ばれる解放用エイリアスである。"""
        self.close()

    def __enter__(self) -> "Xdm1000Ctrl":
        """
        with 文用のエントリ
        """
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        tb,
    ) -> None:
        """
        with 文終了時にワーカーを停止
        """
        self.close()

    # ------------------------------------------------------------------
    # 測定中でも許可する API
    # ------------------------------------------------------------------

    def get_state(self) -> Dict[str, Any]:
        """
        現在の状態を返す。測定中でも呼べる。
        """
        if self.use_process:
            state = dict(self._state)
            state["process_alive"] = self._process.is_alive()
            return state

        state = dict(self._direct_state)
        state["process_alive"] = False
        return state

    def is_running(self) -> bool:
        """
        長時間測定中なら True を返す。
        """
        return self._is_running()

    def stop_job(self) -> Dict[str, Any]:
        """
        実行中の長時間測定に停止要求を出す。測定中でも呼べる。
        """
        if self.use_process:
            self._stop_event.set()
        else:
            self._direct_stop_requested = True
        return self.get_state()

    def get_continuous_result(
        self,
        clear: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        連続測定の結果を返す。測定終了後にまとめて取得する想定
        """
        if self.use_process:
            result = self._result_store.get("continuous")
            if clear and "continuous" in self._result_store:
                del self._result_store["continuous"]
            return result

        result = self._direct_result_store.get("continuous")
        if clear:
            self._direct_result_store["continuous"] = None
        return result

    def get_statistics_result(
        self,
        clear: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        統計モードテストの結果を返す。
        """
        if self.use_process:
            result = self._result_store.get("statistics")
            if clear and "statistics" in self._result_store:
                del self._result_store["statistics"]
            return result

        result = self._direct_result_store.get("statistics")
        if clear:
            self._direct_result_store["statistics"] = None
        return result

    # ------------------------------------------------------------------
    # 測定中は拒否する通常 API
    # remote/local は公開しない。通信モード制御はワーカー内部で完結させる。
    # ------------------------------------------------------------------

    def idn(self) -> str:
        """
        *IDN? を返す。測定中は拒否
        """
        self._require_not_running()
        if self.use_process:
            return self._rpc("idn", timeout=5.0)
        return self.scpi.idn()

    def _reset_scpi_internal(self) -> None:
        """
        内部確認用に *RST を実行

        上位公開 API としては扱わない。通常の利用では呼ばない。
        測定中は拒否する。
        """
        self._require_not_running()
        if self.use_process:
            self._rpc("reset", timeout=10.0)
        else:
            self.scpi.reset()
            self._current_meas_config = None

    def set_meas_mode(
        self,
        kind: MeasureKind,
        range_value: Union[str, int, float] = "AUTO",
        rate: str = "F",
    ) -> Dict[str, Any]:
        """
        測定種別・レンジ・速度を設定。測定中は拒否
        """
        self._require_not_running()

        if self.use_process:
            return self._rpc(
                "set_meas_mode",
                {"kind": kind, "range_value": range_value, "rate": rate},
                timeout=10.0,
            )

        self._configure_meas_direct(
            kind=kind,
            range_value=range_value,
            rate=rate,
        )
        return {
            "kind": kind,
            "range_value": range_value,
            "rate": rate,
        }

    def meas_one_shot(
        self,
        kind: MeasureKind,
        range_value: Union[str, int, float] = "AUTO",
        rate: str = "F",
        settle: float = 0.0,
    ) -> Dict[str, Any]:
        """
        1 shot 測定を実行

        ``kind`` と ``range_value`` と ``rate`` を設定し、必要なら ``settle`` 秒待ってから
        ``MEAS1?`` を 1 回読む。測定中は拒否する。
        """
        self._require_not_running()

        if self.use_process:
            return self._rpc(
                "one_shot",
                {"kind": kind, "range_value": range_value, "rate": rate, "settle": settle},
                timeout=10.0 + max(0.0, settle),
            )

        self._configure_meas_direct(
            kind=kind,
            range_value=range_value,
            rate=rate,
        )
        time.sleep(max(0.0, settle))
        t0 = time.perf_counter()
        before = time.time()
        value = self.scpi.meas_main()
        after = time.time()
        return {
            "kind": kind,
            "range_value": range_value,
            "rate": rate,
            "value": value,
            "host_time_start": before,
            "host_time_end": after,
            "read_elapsed": time.perf_counter() - t0,
        }

    def meas(
        self,
        kind: MeasureKind = "voltage_dc",
        range_value: Union[str, int, float] = "AUTO",
        rate: str = "F",
        settle: float = 0.0,
    ) -> Dict[str, Any]:
        """
        1 shot 測定の短縮名
        """
        return self.meas_one_shot(
            kind=kind,
            range_value=range_value,
            rate=rate,
            settle=settle,
        )

    def meas_voltage_dc(
        self,
        range_value: Union[str, int, float] = "AUTO",
        rate: str = "F",
    ) -> Dict[str, Any]:
        """
        DC 電圧を 1 shot 測定
        """
        return self.meas_one_shot("voltage_dc", range_value, rate)

    def meas_current_dc(
        self,
        range_value: Union[str, int, float] = "AUTO",
        rate: str = "F",
    ) -> Dict[str, Any]:
        """
        DC 電流を 1 shot 測定
        """
        return self.meas_one_shot("current_dc", range_value, rate)

    # ------------------------------------------------------------------
    # 長時間測定 API
    # ------------------------------------------------------------------

    def start_continuous_meas(
        self,
        kind: MeasureKind,
        duration: float,
        range_value: Union[str, int, float] = "AUTO",
        rate: str = "F",
        interval: float = 0.0,
        settle: float = 0.0,
    ) -> Dict[str, Any]:
        """
        擬似 continuous 測定を開始する。

        ``duration`` 秒だけ、ワーカープロセス側で ``MEAS1?`` を繰り返す。
        ``interval=0`` の場合は Python 側では待たず、装置とシリアル通信が許す範囲で
        最速に読む。各サンプルには host 側の時刻を付与する。

        このメソッドはワーカーが job を受理した時点で戻る。結果は終了後に
        ``get_continuous_result()`` で取得する。
        """
        self._require_not_running()

        if self.use_process:
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

        if duration <= 0:
            raise ValueError("duration は正の値でなければならない。")
        if interval < 0:
            raise ValueError("interval は 0 以上でなければならない。")

        job_id = uuid.uuid4().hex
        self._direct_begin_job(job_id, "continuous")
        self._configure_meas_direct(
            kind=kind,
            range_value=range_value,
            rate=rate,
        )
        time.sleep(max(0.0, settle))

        started_at = time.time()
        deadline = started_at + duration
        samples = []

        while True:
            now = time.time()
            if now >= deadline:
                break
            if self._direct_stop_requested:
                break

            t0 = time.perf_counter()
            before = time.time()
            value = self.scpi.meas_main()
            after = time.time()

            samples.append(
                {
                    "host_time_start": before,
                    "host_time_end": after,
                    "read_elapsed": time.perf_counter() - t0,
                    "value": value,
                }
            )

            if interval > 0:
                next_time = before + interval
                remain = next_time - time.time()
                if remain > 0:
                    time.sleep(remain)

        finished_at = time.time()
        result = {
            "job_id": job_id,
            "kind": kind,
            "range_value": range_value,
            "rate": rate,
            "interval": interval,
            "duration": duration,
            "requested_stop": bool(self._direct_stop_requested),
            "host_time_start": started_at,
            "host_time_end": finished_at,
            "samples": samples,
            "count": len(samples),
        }
        self._direct_result_store["continuous"] = result
        self._direct_finish_job()
        return {"job_id": job_id}

    def start_statistics_mode(
        self,
        kind: MeasureKind,
        duration: float,
        range_value: Union[str, int, float] = "AUTO",
        rate: str = "F",
        settle: float = 0.0,
    ) -> Dict[str, Any]:
        """statistics モードのテスト測定を開始する。

        XDM1000 の ``CALCulate:AVERage:ALL?`` は minimum, maximum, average, count を
        返す統計機能である。ただし statistics の clear/start 条件が未確認なので、
        現段階では duration 秒の厳密な平均値 API ではなく、テスト機能として扱う。
        """
        self._require_not_running()

        if self.use_process:
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

        if duration <= 0:
            raise ValueError("duration は正の値でなければならない。")

        job_id = uuid.uuid4().hex
        self._direct_begin_job(job_id, "statistics")
        self._configure_meas_direct(
            kind=kind,
            range_value=range_value,
            rate=rate,
        )
        time.sleep(max(0.0, settle))

        values = []
        started_at = time.time()
        deadline = started_at + duration

        while True:
            now = time.time()
            if now >= deadline:
                break
            if self._direct_stop_requested:
                break
            values.append(self.scpi.meas_main())

        finished_at = time.time()
        if values:
            minimum = min(values)
            maximum = max(values)
            average = sum(values) / len(values)
            count = len(values)
        else:
            minimum = None
            maximum = None
            average = None
            count = 0

        result = {
            "job_id": job_id,
            "kind": kind,
            "range_value": range_value,
            "rate": rate,
            "duration": duration,
            "requested_stop": bool(self._direct_stop_requested),
            "host_time_start": started_at,
            "host_time_end": finished_at,
            "minimum": minimum,
            "maximum": maximum,
            "average": average,
            "count": count,
            "values": values,
        }
        self._direct_result_store["statistics"] = result
        self._direct_finish_job()
        return {"job_id": job_id}

    def wait_until_done(self, poll_interval: float = 0.2) -> Dict[str, Any]:
        """
        running が終わるまで状態を表示しながら待つ。
        """
        while True:
            state = self.get_state()
            print("STATE:", state)
            if not state.get("running", False):
                return state
            time.sleep(poll_interval)


def _example_main() -> None:
    """上位制御クラスの動作確認用サンプルである。

    実行例::

        python xdm1000_ctrl.py /dev/cu.usbserial-140 --mode voltage_dc --duration 5

    1 shot 測定、擬似 continuous 測定、statistics テストを順に実行する。
    """
    # ----------------------------------------------------------------------
    # 接続設定
    # ----------------------------------------------------------------------

    # PORT = "/dev/cu.usbserial-140"
    PORT = "/dev/cu.usbserial-10"
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

    dmm.wait_until_done()

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

    # _wait_until_done(dmm)
    print(dmm.get_statistics_result(clear=True))


if __name__ == "__main__":
    _example_main()
