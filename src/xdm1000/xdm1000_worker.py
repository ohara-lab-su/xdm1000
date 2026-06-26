#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""XDM1000 デジタルマルチメータ用ワーカープロセス実装である。

本ファイルはプロセス分離時にシリアルポートを保持する実体である。
SCPI 層は SCPI コマンドの薄いラッパに留め、ここでは ctrl 層から渡された
上位 API 操作を実機操作へ変換する。
"""

import math
import time
import traceback

from xdm1000.xdm1000_scpi import Xdm1000Scpi


MODE_TO_SCPI_FUNCTION = {
    "voltage_dc": "VOLT",
    "voltage_ac": "VOLT AC",
    "current_dc": "CURR",
    "current_ac": "CURR AC",
    "resistance": "RES",
    "fresistance": "FRES",
    "frequency": "FREQ",
    "period": "PER",
    "capacitance": "CAP",
    "temperature_rtd": "TEMP",
    "diode": "DIOD",
    "continuity": "CONT",
}


def _validate_mode(mode):
    """上位 API の mode 名を SCPI の FUNCtion パラメータへ変換する。"""
    if mode not in MODE_TO_SCPI_FUNCTION:
        raise ValueError("未対応の測定モードである: {0!r}".format(mode))
    return MODE_TO_SCPI_FUNCTION[mode]


def _validate_integration_speed(speed):
    """XDM1000 の RATE パラメータを検証する。"""
    speed = str(speed).upper()
    if speed not in ("F", "M", "S"):
        raise ValueError("integration_speed は 'F', 'M', 'S' のいずれかでなければならない。")
    return speed


def _sample_clock(t0_perf):
    """測定時刻をホスト時刻と相対時刻で返す。"""
    perf = time.perf_counter()
    return {
        "host_time": time.time(),
        "host_perf": perf,
        "t_rel": perf - t0_perf,
    }



def _continuous_result(
    job_id,
    ok,
    stopped,
    mode,
    range_value,
    auto_range,
    integration_speed,
    interval,
    duration,
    count_limit,
    samples,
    started_at,
    finished_at=None,
):
    """連続測定結果 dict を作成する。

    測定中も終了後も同じ構造を使う。get_result() はこの dict を返す。
    """
    return {
        "type": "continuous",
        "job_id": job_id,
        "ok": ok,
        "running": finished_at is None,
        "stopped": stopped,
        "mode": mode,
        "range_value": range_value,
        "auto_range": auto_range,
        "integration_speed": integration_speed,
        "continue_interval": interval,
        "continue_duration": duration,
        "continue_count": count_limit,
        "started_at": started_at,
        "finished_at": finished_at,
        "samples": list(samples),
    }


class _Xdm1000Worker(object):
    """XDM1000 を子プロセス側で制御するワーカーである。"""

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
        logger=None,
        log_level=None,
        config=None,
    ):
        if logger is None:
            import logging

            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            logger = logging.getLogger(__name__)

        self.command_q = command_q
        self.response_q = response_q
        self.state = state
        self.result_store = result_store
        self.stop_event = stop_event
        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate
        self.logger = logger
        self.log_level = log_level
        self.config = config
        self.scpi = None

        self._mode = None
        self._range_value = None
        self._auto_range = None
        self._integration_speed = None
        self._continue_interval = 0.0
        self._continue_duration = None
        self._continue_count = None

        if self.config is not None:
            self.port = getattr(self.config, "PORT", self.port)
            self.timeout = getattr(self.config, "TIMEOUT", self.timeout)
            self.baudrate = getattr(self.config, "BAUDRATE", self.baudrate)

    def set_idle(self, message="idle"):
        """共有 state を idle にする。"""
        self.state["running"] = False
        self.state["job_id"] = None
        self.state["job_type"] = None
        self.state["started_at"] = None
        self.state["finished_at"] = None
        self.state["error"] = None
        self.state["traceback"] = None
        self.state["message"] = message
        self.state["stop_requested"] = False
        self.state["worker_alive"] = True
        self.state["port"] = self.port
        self.state["baudrate"] = self.baudrate
        self._publish_config_state()

    def set_running(self, job_id, job_type, args):
        """共有 state を running にする。"""
        self.stop_event.clear()
        self.state["running"] = True
        self.state["stop_requested"] = False
        self.state["job_id"] = job_id
        self.state["job_type"] = job_type
        self.state["started_at"] = time.time()
        self.state["finished_at"] = None
        self.state["error"] = None
        self.state["traceback"] = None
        self.state["message"] = "running"
        self.state["args"] = dict(args)
        self._publish_config_state()

    def finish(self, message="finished"):
        """共有 state を終了状態にする。"""
        self.state["running"] = False
        self.state["finished_at"] = time.time()
        self.state["message"] = message
        self.state["stop_requested"] = False
        self._publish_config_state()

    def fail(self, exc):
        """共有 state にエラーを記録する。"""
        self.state["running"] = False
        self.state["finished_at"] = time.time()
        self.state["error"] = repr(exc)
        self.state["traceback"] = traceback.format_exc()
        self.state["message"] = "failed"
        self.state["stop_requested"] = False

    def _publish_config_state(self):
        """現在の設定キャッシュを共有 state に反映する。"""
        self.state["mode"] = self._mode
        self.state["range_value"] = self._range_value
        self.state["auto_range"] = self._auto_range
        self.state["integration_speed"] = self._integration_speed
        self.state["continue_interval"] = self._continue_interval
        self.state["continue_duration"] = self._continue_duration
        self.state["continue_count"] = self._continue_count

    def open(self):
        """SCPI 接続を開く。"""
        try:
            self.scpi = Xdm1000Scpi(
                port=self.port,
                timeout=self.timeout,
                baudrate=self.baudrate,
                logger=self.logger,
                log_level=self.log_level,
                config=self.config,
            )
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
        """SCPI 接続を閉じる。"""
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
        """正常応答を返す。"""
        self.response_q.put({"req_id": req_id, "ok": True, "result": result})

    def put_error(self, req_id, exc):
        """異常応答を返す。"""
        self.response_q.put(
            {
                "req_id": req_id,
                "ok": False,
                "error": repr(exc),
                "traceback": traceback.format_exc(),
            }
        )

    def _require_mode(self):
        """測定モード未設定なら例外にする。"""
        if self._mode is None:
            raise ValueError("先に set_mode() で測定モードを設定する必要がある。")

    def handle_idn(self, req_id):
        """*IDN? を返す。"""
        self.put_ok(req_id, self.scpi.idn())

    def handle_reset(self, req_id):
        """*RST を実行する。"""
        self.scpi.reset()
        self._mode = None
        self._range_value = None
        self._auto_range = None
        self._integration_speed = None
        self.result_store["result"] = None
        self._publish_config_state()
        self.put_ok(req_id, None)

    def handle_set_mode(self, req_id, args):
        """測定モードを設定する。"""
        mode = args["mode"]
        function = _validate_mode(mode)
        self.scpi.set_function(function)
        self._mode = mode
        self._range_value = None
        self._auto_range = None
        self._publish_config_state()
        if req_id is not None:
            self.put_ok(req_id, {"mode": mode})

    def handle_set_range(self, req_id, args):
        """測定レンジを設定する。"""
        range_value = args["range_value"]
        self._require_mode()
        self.scpi.set_range(range_value)
        self._range_value = range_value
        self._auto_range = False
        self._publish_config_state()
        self.put_ok(req_id, {"range_value": range_value})

    def handle_set_auto_range(self, req_id, args):
        """オートレンジを設定する。"""
        enabled = bool(args["enabled"])
        self._require_mode()
        if enabled:
            self.scpi.set_auto_range(True)
            self._auto_range = True
        else:
            if self._range_value is None:
                raise ValueError("auto_range=False にするには、先に set_range() で手動レンジを設定する必要がある。")
            self.scpi.set_range(self._range_value)
            self._auto_range = False
        self._publish_config_state()
        self.put_ok(req_id, {"auto_range": self._auto_range})

    def handle_set_integration_speed(self, req_id, args):
        """内部測定速度を設定する。"""
        speed = _validate_integration_speed(args["speed"])
        self.scpi.set_rate(speed)
        self._integration_speed = speed
        self._publish_config_state()
        self.put_ok(req_id, {"integration_speed": speed})

    def handle_set_continue_interval(self, req_id, args):
        """連続測定の測定間隔を設定する。"""
        interval = float(args["interval"])
        if interval < 0.0:
            raise ValueError("interval は 0 以上でなければならない。")
        self._continue_interval = interval
        self._publish_config_state()
        self.put_ok(req_id, {"continue_interval": interval})

    def handle_set_continue_duration(self, req_id, args):
        """連続測定の最大時間を設定する。"""
        duration = args.get("duration")
        if duration is None:
            self._continue_duration = None
        else:
            duration = float(duration)
            if duration <= 0.0:
                raise ValueError("duration は正の値でなければならない。")
            self._continue_duration = duration
        self._publish_config_state()
        self.put_ok(req_id, {"continue_duration": self._continue_duration})

    def handle_set_continue_count(self, req_id, args):
        """連続測定の最大回数を設定する。"""
        count = args.get("count")
        if count is None:
            self._continue_count = None
        else:
            count = int(count)
            if count <= 0:
                raise ValueError("count は正の整数でなければならない。")
            self._continue_count = count
        self._publish_config_state()
        self.put_ok(req_id, {"continue_count": self._continue_count})

    def handle_meas(self, req_id, args):
        """現在設定で 1 回測定する。"""
        self._require_mode()
        wait = args.get("wait")
        if wait is not None:
            wait = float(wait)
            if wait > 0.0:
                time.sleep(wait)

        t0 = time.perf_counter()
        before = _sample_clock(t0)
        value = self.scpi.meas_main()
        after = _sample_clock(t0)
        result = {
            "type": "single",
            "mode": self._mode,
            "range_value": self._range_value,
            "auto_range": self._auto_range,
            "integration_speed": self._integration_speed,
            "value": value,
            "host_time_start": before["host_time"],
            "host_time_end": after["host_time"],
            "read_elapsed": after["host_perf"] - before["host_perf"],
        }
        self.result_store["result"] = result
        self.put_ok(req_id, result)

    def handle_meas_continue(self, req_id, args):
        """現在設定で連続測定する。"""
        self._require_mode()
        wait = args.get("wait")
        if wait is not None:
            wait = float(wait)
            if wait > 0.0:
                time.sleep(wait)

        duration = self._continue_duration
        count_limit = self._continue_count
        interval = float(self._continue_interval or 0.0)
        if duration is None and count_limit is None:
            raise ValueError("meas_continue() の前に set_continue_duration() または set_continue_count() を設定する必要がある。")

        job_id = args["job_id"]
        self.set_running(job_id, "continuous", args)
        self.put_ok(req_id, {"job_id": job_id})

        samples = []
        t0 = time.perf_counter()
        deadline = None
        if duration is not None:
            deadline = t0 + float(duration)

        stopped = False
        try:
            index = 0
            while True:
                if self.stop_event.is_set():
                    stopped = True
                    self.state["stop_requested"] = True
                    break

                now = time.perf_counter()
                if deadline is not None and now >= deadline:
                    break
                if count_limit is not None and index >= count_limit:
                    break

                before = _sample_clock(t0)
                value = self.scpi.meas_main()
                after = _sample_clock(t0)
                samples.append(
                    {
                        "index": index,
                        "value": value,
                        "host_time_start": before["host_time"],
                        "host_time_end": after["host_time"],
                        "read_elapsed": after["host_perf"] - before["host_perf"],
                        "t_rel_start": before["t_rel"],
                        "t_rel_end": after["t_rel"],
                    }
                )
                index += 1

                self.result_store["result"] = _continuous_result(
                    job_id=job_id,
                    ok=True,
                    stopped=False,
                    mode=self._mode,
                    range_value=self._range_value,
                    auto_range=self._auto_range,
                    integration_speed=self._integration_speed,
                    interval=interval,
                    duration=duration,
                    count_limit=count_limit,
                    samples=samples,
                    started_at=self.state.get("started_at"),
                    finished_at=None,
                )
                self.state["sample_count"] = len(samples)
                self.state["latest_value"] = value
                self.state["latest_host_time"] = after["host_time"]
                self.state["elapsed"] = after["t_rel"]

                if interval > 0.0:
                    next_target = before["host_perf"] + interval
                    while True:
                        if self.stop_event.is_set():
                            stopped = True
                            self.state["stop_requested"] = True
                            break

                        remain = next_target - time.perf_counter()
                        if remain <= 0.0:
                            break
                        time.sleep(min(remain, 0.001))

                    if stopped:
                        break

            result = _continuous_result(
                job_id=job_id,
                ok=True,
                stopped=stopped,
                mode=self._mode,
                range_value=self._range_value,
                auto_range=self._auto_range,
                integration_speed=self._integration_speed,
                interval=interval,
                duration=duration,
                count_limit=count_limit,
                samples=samples,
                started_at=self.state.get("started_at"),
                finished_at=time.time(),
            )
            self.result_store["result"] = result
            if stopped:
                self.finish("stopped")
            else:
                self.finish("finished")
        except BaseException as exc:
            self.result_store["result"] = {
                "type": "continuous",
                "job_id": job_id,
                "ok": False,
                "error": repr(exc),
                "traceback": traceback.format_exc(),
            }
            self.fail(exc)

    def handle_command(self, command):
        """親プロセスからのコマンドを処理する。"""
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
            elif name == "set_mode":
                self.handle_set_mode(req_id, args)
            elif name == "set_range":
                self.handle_set_range(req_id, args)
            elif name == "set_auto_range":
                self.handle_set_auto_range(req_id, args)
            elif name == "set_integration_speed":
                self.handle_set_integration_speed(req_id, args)
            elif name == "set_continue_interval":
                self.handle_set_continue_interval(req_id, args)
            elif name == "set_continue_duration":
                self.handle_set_continue_duration(req_id, args)
            elif name == "set_continue_count":
                self.handle_set_continue_count(req_id, args)
            elif name == "meas":
                self.handle_meas(req_id, args)
            elif name == "meas_continue":
                self.handle_meas_continue(req_id, args)
            else:
                raise ValueError("未知の worker command である: {0!r}".format(name))
        except BaseException as exc:
            self.put_error(req_id, exc)

        return True

    def run(self):
        """ワーカーメインループを実行する。"""
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
