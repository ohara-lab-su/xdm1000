#!/usr/bin/env python
from typing import Any, Dict, List, Optional, Union
import multiprocessing as mp
import traceback
import time
import math

from xdm1000.xdm1000_scpi import Xdm1000Scpi


class MeasurementConfig(object):
    """
    worker 側で装置へ反映済みの測定条件を保持する。
    """

    def __init__(
        self,
        kind,
        range_value="AUTO",
        rate="F",
    ):
        self.kind = kind
        self.range_value = range_value
        self.rate = rate

    def equals(
        self,
        other,
    ):
        if other is None:
            return False
        if self.kind != other.kind:
            return False
        if self.range_value != other.range_value:
            return False
        if self.rate != other.rate:
            return False
        return True


def _sample_clock(t0_perf):
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
    scpi,
    kind,
    range_value="AUTO",
):
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
        raise ValueError("未対応の測定種別である: {0!r}".format(kind))


def _calc_stats(values):
    """
    サーバー側で取得した測定値リストから基本統計を計算する。
    """
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


class _Xdm1000Worker(object):
    """子プロセス側で SCPI 実行を担当する worker 実体である。

    親側の ``Xdm1000Ctrl`` は queue、process、state、result を管理する。
    この worker は子プロセス内でだけ生成され、``Xdm1000Scpi`` を保持して
    SCPI コマンドと長時間測定を実行する。
    """

    def __init__(
        self,
        command_q,
        response_q,
        state,
        result_store,
        stop_event,
        port,
        timeout,
        baudrate,
        logger_name=None,
    ):
        """worker に必要な共有オブジェクトと接続情報を保持する。"""
        self.command_q = command_q
        self.response_q = response_q
        self.state = state
        self.result_store = result_store
        self.stop_event = stop_event
        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate
        self.logger_name = logger_name
        self.scpi = None
        self._device_config = None

    def set_idle(self, message="idle"):
        """共有 state を idle に戻す。"""
        self.state["running"] = False
        self.state["job_id"] = None
        self.state["job_type"] = None
        self.state["started_at"] = None
        self.state["finished_at"] = None
        self.state["error"] = None
        self.state["traceback"] = None
        self.state["message"] = message

    def set_running(self, job_id, job_type, args):
        """共有 state を running にする。"""
        self.state["running"] = True
        self.state["job_id"] = job_id
        self.state["job_type"] = job_type
        self.state["started_at"] = time.time()
        self.state["finished_at"] = None
        self.state["error"] = None
        self.state["traceback"] = None
        self.state["message"] = "running"
        self.state["meas_kind"] = args.get("kind")
        self.state["range_value"] = args.get("range_value", "AUTO")
        self.state["rate"] = args.get("rate", "F")
        self.state["duration"] = args.get("duration")
        self.state["interval"] = args.get("interval")
        self.state["sample_count"] = 0
        self.state["last_value"] = None
        self.state["last_host_time"] = None

    def finish(self, message="finished"):
        """共有 state を終了状態にする。"""
        self.state["running"] = False
        self.state["finished_at"] = time.time()
        self.state["message"] = message

    def fail(self, exc):
        """共有 state にワーカー例外を記録する。"""
        self.state["running"] = False
        self.state["finished_at"] = time.time()
        self.state["error"] = "".join(
            traceback.format_exception_only(type(exc), exc)
        ).strip()
        self.state["traceback"] = traceback.format_exc()
        self.state["message"] = "error"

    def open(self):
        """SCPI 接続を開き、remote mode に入る。"""
        try:
            self.scpi = Xdm1000Scpi(
                port=self.port,
                timeout=self.timeout,
                baudrate=self.baudrate,
            )
            # 上位制御クラスでは remote/local を公開しない。
            # 通信モード制御はワーカー起動・終了時の内部処理として扱う。
            self.scpi.remote()

            self.state["worker_alive"] = True
            self.state["port"] = self.port
            self.state["baudrate"] = self.baudrate
            self.set_idle("worker_ready")
            return True

        except BaseException as exc:
            self.state["worker_alive"] = False
            self.state["error"] = repr(exc)
            self.state["traceback"] = traceback.format_exc()
            return False

    def close(self):
        """SCPI 接続を local に戻して閉じる。"""
        try:
            if self.scpi is not None:
                try:
                    self.scpi.local()
                except Exception:
                    pass
                self.scpi.close()
        finally:
            self.state["worker_alive"] = False

    def put_ok(self, req_id, result=None):
        """正常応答を response queue に返す。"""
        self.response_q.put({"req_id": req_id, "ok": True, "result": result})

    def put_error(self, req_id, exc):
        """例外応答を response queue に返す。"""
        self.response_q.put(
            {
                "req_id": req_id,
                "ok": False,
                "error": repr(exc),
                "traceback": traceback.format_exc(),
            }
        )

    def _apply_meas_config_if_needed(
        self,
        kind,
        range_value="AUTO",
        rate="F",
    ):
        """
        必要なときだけ測定条件を装置へ反映する。
        """
        config = MeasurementConfig(
            kind=kind,
            range_value=range_value,
            rate=rate,
        )
        if config.equals(self._device_config):
            return config

        _configure_meas(self.scpi, kind, range_value)
        self.scpi.set_rate(rate)
        self._device_config = config
        return config

    def handle_idn(self, req_id):
        """*IDN? を実行する。"""
        self.put_ok(req_id, self.scpi.idn())

    def handle_reset(self, req_id):
        """*RST を実行する。"""
        self.scpi.reset()
        self._device_config = None
        self.put_ok(req_id, None)

    def handle_set_meas_mode(self, req_id, args):
        """測定条件を設定する。"""
        config = self._apply_meas_config_if_needed(
            args["kind"],
            args.get("range_value", "AUTO"),
            args.get("rate", "F"),
        )
        self.state["meas_kind"] = config.kind
        self.state["range_value"] = config.range_value
        self.state["rate"] = config.rate
        self.put_ok(req_id, dict(args))

    def handle_one_shot(self, req_id, args):
        """1 shot 測定を実行する。"""
        config = self._apply_meas_config_if_needed(
            args["kind"],
            args.get("range_value", "AUTO"),
            args.get("rate", "F"),
        )
        time.sleep(float(args.get("settle", 0.0)))
        t0 = time.perf_counter()
        before = _sample_clock(t0)
        value = self.scpi.meas_main()
        after = _sample_clock(t0)
        result = {
            "kind": config.kind,
            "range_value": config.range_value,
            "rate": config.rate,
            "value": value,
            "host_time_start": before["host_time"],
            "host_time_end": after["host_time"],
            "read_elapsed": after["host_perf"] - before["host_perf"],
        }
        self.put_ok(req_id, result)

    def handle_start_continuous(self, req_id, args):
        """擬似 continuous 測定を実行する。"""
        job_id = args["job_id"]
        duration = float(args["duration"])
        interval = float(args.get("interval", 0.0))
        if duration <= 0:
            raise ValueError("duration は正の値でなければならない。")
        if interval < 0:
            raise ValueError("interval は 0 以上でなければならない。")

        self.set_running(job_id, "continuous", args)
        self.stop_event.clear()
        config = self._apply_meas_config_if_needed(
            args["kind"],
            args.get("range_value", "AUTO"),
            args.get("rate", "F"),
        )
        time.sleep(float(args.get("settle", 0.0)))
        self.put_ok(req_id, {"job_id": job_id})

        samples = []
        t0 = time.perf_counter()
        deadline = t0 + duration
        index = 0
        try:
            while time.perf_counter() < deadline and not self.stop_event.is_set():
                s0 = _sample_clock(t0)
                value = self.scpi.meas_main()
                s1 = _sample_clock(t0)
                sample = {
                    "index": index,
                    "kind": config.kind,
                    "value": value,
                    "host_time_start": s0["host_time"],
                    "host_time_end": s1["host_time"],
                    "t_rel_start": s0["t_rel"],
                    "t_rel_end": s1["t_rel"],
                    "read_elapsed": s1["host_perf"] - s0["host_perf"],
                }
                samples.append(sample)
                index += 1
                self.state["sample_count"] = index
                self.state["last_value"] = value
                self.state["last_host_time"] = s1["host_time"]

                if interval > 0:
                    # interval は「読み取り完了後から次回開始までの待ち時間」である。
                    # interval=0 の場合は Python 側では待たず、装置と通信が許す限り最速で読む。
                    sleep_until = time.perf_counter() + interval
                    while time.perf_counter() < sleep_until:
                        if self.stop_event.is_set():
                            break
                        time.sleep(min(0.005, sleep_until - time.perf_counter()))

        except BaseException as exc:
            self.result_store["continuous"] = {
                "job_id": job_id,
                "ok": False,
                "error": repr(exc),
                "traceback": traceback.format_exc(),
                "samples": samples,
            }
            self.fail(exc)
        else:
            values = [float(s["value"]) for s in samples]
            self.result_store["continuous"] = {
                "job_id": job_id,
                "ok": True,
                "stopped": self.stop_event.is_set(),
                "kind": config.kind,
                "range_value": config.range_value,
                "rate": config.rate,
                "duration_requested": duration,
                "interval_requested": interval,
                "settle": float(args.get("settle", 0.0)),
                "samples": samples,
                "stats": _calc_stats(values),
                "started_at": self.state.get("started_at"),
                "finished_at": time.time(),
            }
            if self.stop_event.is_set():
                self.finish("stopped")
            else:
                self.finish("finished")

    def handle_start_statistics(self, req_id, args):
        """statistics モードのテスト測定を実行する。"""
        job_id = args["job_id"]
        duration = float(args["duration"])
        if duration <= 0:
            raise ValueError("duration は正の値でなければならない。")

        self.set_running(job_id, "statistics", args)
        self.stop_event.clear()
        config = self._apply_meas_config_if_needed(
            args["kind"],
            args.get("range_value", "AUTO"),
            args.get("rate", "F"),
        )
        time.sleep(float(args.get("settle", 0.0)))
        self.put_ok(req_id, {"job_id": job_id})

        try:
            # 統計モードは現段階ではテスト用である。
            # XDM1000 の statistics がいつ clear/start されるかは実機確認が必要である。
            # したがって、ここでは CALC:FUNC AVERage を設定して duration 秒待ち、
            # CALC:AVERage:ALL? を読むだけに留める。
            self.scpi.set_calc_function("AVERage")
            t0 = time.perf_counter()
            deadline = t0 + duration
            while time.perf_counter() < deadline and not self.stop_event.is_set():
                time.sleep(min(0.05, deadline - time.perf_counter()))
            stats = self.scpi.get_average_all()
            self.result_store["statistics"] = {
                "job_id": job_id,
                "ok": True,
                "stopped": self.stop_event.is_set(),
                "kind": config.kind,
                "range_value": config.range_value,
                "rate": config.rate,
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
                "started_at": self.state.get("started_at"),
                "finished_at": time.time(),
            }
            if self.stop_event.is_set():
                self.finish("stopped")
            else:
                self.finish("finished")
        except BaseException as exc:
            self.result_store["statistics"] = {
                "job_id": job_id,
                "ok": False,
                "error": repr(exc),
                "traceback": traceback.format_exc(),
            }
            self.fail(exc)

    def handle_command(self, command):
        """command queue から受け取った 1 コマンドを処理する。

        ``False`` を返した場合は worker loop を終了する。
        """
        req_id = command.get("req_id")
        name = command.get("cmd")
        args = command.get("args", {})

        try:
            if name == "shutdown":
                self.put_ok(req_id, None)
                return False

            if name == "idn":
                self.handle_idn(req_id)
            elif name == "reset":
                self.handle_reset(req_id)
            elif name == "set_meas_mode":
                self.handle_set_meas_mode(req_id, args)
            elif name == "one_shot":
                self.handle_one_shot(req_id, args)
            elif name == "start_continuous":
                self.handle_start_continuous(req_id, args)
            elif name == "start_statistics":
                self.handle_start_statistics(req_id, args)
            else:
                raise ValueError("未知の worker command である: {0!r}".format(name))

        except BaseException as exc:
            self.put_error(req_id, exc)

        return True

    def run(self):
        """worker process のメインループである。"""
        if not self.open():
            return

        try:
            while True:
                try:
                    command = self.command_q.get()
                    if not self.handle_command(command):
                        break
                except BaseException:
                    self.state["worker_loop_error"] = traceback.format_exc()
        finally:
            self.close()
