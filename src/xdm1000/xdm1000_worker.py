#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
XDM1000 の process worker である。

親側の Xdm1000Ctrl は queue、process、state、result を管理する。
この worker は子プロセス内でだけ生成され、Xdm1000Scpi を保持して
SCPI コマンドと長時間測定を実行する。

設計方針
--------

* logger 実体が無いときだけ x_logger / logging を使う。
* logger 名は ``logger_name`` を通して受け取れる。
* config があれば config を優先する。
* kind / range_value / rate が現在設定と異なるときだけ設定し直す。
* ctrl が現在設定の正本を持ち、worker は装置反映済みキャッシュだけを持つ。
* 同じ worker の寿命中は装置反映済みキャッシュを保持し続ける。
* Python 3.6 で動く書き方を使う。
"""

import traceback
import time
import math

try:
    from x_logger import get_logger
except Exception:
    get_logger = None

from xdm1000.xdm1000_scpi import Xdm1000Scpi


class MeasurementConfig(object):
    """現在の測定条件を保持する。"""

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

    def to_dict(
        self,
    ):
        return {
            "kind": self.kind,
            "range_value": self.range_value,
            "rate": self.rate,
        }


def _sample_clock(
    t0_perf,
):
    """ホスト PC 側の時刻情報を作る。"""
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


def _calc_stats(
    values,
):
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
    average = sum(values) / float(count)
    variance = sum((x - average) ** 2 for x in values) / float(count)
    return {
        "count": count,
        "minimum": min(values),
        "maximum": max(values),
        "average": average,
        "stdev_population": math.sqrt(variance),
    }


class _Xdm1000Worker(object):
    """子プロセス側で SCPI 実行を担当する worker 実体である。"""

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
        """worker に必要な共有オブジェクトと接続情報を保持する。"""
        self.log_level = log_level
        if logger is None:
            import logging

            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            logger = logging.getLogger(__name__)

        self.logger = logger
        self.config = config

        if self.config is not None:
            port = getattr(self.config, "PORT", port)
            timeout = getattr(self.config, "TIMEOUT", timeout)
            baudrate = getattr(self.config, "BAUDRATE", baudrate)

        self.command_q = command_q
        self.response_q = response_q
        self.state = state
        self.result_store = result_store
        self.stop_event = stop_event
        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate
        self.scpi = None

        self._device_config = None

    def set_idle(
        self,
        message="idle",
    ):
        self.state["running"] = False
        self.state["job_id"] = None
        self.state["job_type"] = None
        self.state["started_at"] = None
        self.state["finished_at"] = None
        self.state["error"] = None
        self.state["traceback"] = None
        self.state["message"] = message
        self.state["worker_alive"] = True
        self.state["port"] = self.port
        self.state["baudrate"] = self.baudrate

    def set_running(
        self,
        job_id,
        job_type,
        args,
    ):
        self.state["running"] = True
        self.state["job_id"] = job_id
        self.state["job_type"] = job_type
        self.state["started_at"] = time.time()
        self.state["finished_at"] = None
        self.state["error"] = None
        self.state["traceback"] = None
        self.state["message"] = "running"
        self.state["args"] = dict(args)

    def finish(
        self,
        message="finished",
    ):
        self.state["running"] = False
        self.state["finished_at"] = time.time()
        self.state["message"] = message

    def fail(
        self,
        exc,
    ):
        self.state["running"] = False
        self.state["finished_at"] = time.time()
        self.state["error"] = repr(exc)
        self.state["traceback"] = traceback.format_exc()
        self.state["message"] = "failed"

    def open(
        self,
    ):
        """SCPI 接続を開き、remote mode に入る。"""
        try:
            self.scpi = Xdm1000Scpi(
                port=self.port,
                timeout=self.timeout,
                baudrate=self.baudrate,
                logger=self.logger,
                logger_name=self.logger_name,
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

    def close(
        self,
    ):
        """SCPI 接続を local に戻して閉じる。"""
        try:
            if self.scpi is not None:
                try:
                    self.scpi.local()
                except Exception:
                    pass
                self.scpi.close()
        finally:
            try:
                self.state["worker_alive"] = False
            except Exception:
                pass

    def put_ok(
        self,
        req_id,
        result=None,
    ):
        self.response_q.put({"req_id": req_id, "ok": True, "result": result})

    def put_error(
        self,
        req_id,
        exc,
    ):
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
        config,
    ):
        """必要なときだけ測定条件を装置へ反映する。"""
        if config.equals(self._device_config):
            return

        if self._device_config is None:
            need_configure = True
            need_rate = True
        else:
            need_configure = (
                self._device_config.kind != config.kind
                or self._device_config.range_value != config.range_value
            )
            need_rate = self._device_config.rate != config.rate

        if need_configure:
            _configure_meas(
                self.scpi,
                config.kind,
                config.range_value,
            )

        if need_rate:
            self.scpi.set_rate(config.rate)

        if need_configure or need_rate:
            self._device_config = config

    def handle_idn(
        self,
        req_id,
    ):
        self.put_ok(req_id, self.scpi.idn())

    def handle_reset(
        self,
        req_id,
    ):
        self.scpi.reset()
        self._device_config = None
        self.put_ok(req_id, None)

    def handle_set_meas_mode(
        self,
        req_id,
        args,
    ):
        config = MeasurementConfig(
            kind=args["kind"],
            range_value=args.get("range_value", "AUTO"),
            rate=args.get("rate", "F"),
        )
        self._apply_meas_config_if_needed(config)
        self.state["meas_kind"] = config.kind
        self.state["range_value"] = config.range_value
        self.state["rate"] = config.rate
        self.put_ok(req_id, config.to_dict())

    def handle_one_shot(
        self,
        req_id,
        args,
    ):
        config = MeasurementConfig(
            kind=args["kind"],
            range_value=args.get("range_value", "AUTO"),
            rate=args.get("rate", "F"),
        )
        self._apply_meas_config_if_needed(config)

        settle = float(args.get("settle", 0.0))
        if settle > 0.0:
            time.sleep(settle)

        t0 = time.perf_counter()
        before = _sample_clock(t0)
        value = self.scpi.meas_main()
        after = _sample_clock(t0)

        self.put_ok(
            req_id,
            {
                "kind": config.kind,
                "range_value": config.range_value,
                "rate": config.rate,
                "value": value,
                "host_time_start": before["host_time"],
                "host_time_end": after["host_time"],
                "read_elapsed": after["host_perf"] - before["host_perf"],
            },
        )

    def handle_start_continuous(
        self,
        req_id,
        args,
    ):
        job_id = args["job_id"]
        duration = float(args["duration"])
        interval = float(args.get("interval", 0.0))
        settle = float(args.get("settle", 0.0))

        if duration <= 0.0:
            raise ValueError("duration は正の値でなければならない。")
        if interval < 0.0:
            raise ValueError("interval は 0 以上でなければならない。")

        config = MeasurementConfig(
            kind=args["kind"],
            range_value=args.get("range_value", "AUTO"),
            rate=args.get("rate", "F"),
        )
        self._apply_meas_config_if_needed(config)

        self.set_running(job_id, "continuous", args)
        self.stop_event.clear()
        self.put_ok(req_id, {"job_id": job_id})

        if settle > 0.0:
            time.sleep(settle)

        started_at = time.time()
        deadline = started_at + duration
        samples = []

        try:
            while True:
                now = time.time()
                if now >= deadline:
                    break
                if self.stop_event.is_set():
                    break

                t0 = time.perf_counter()
                before = _sample_clock(t0)
                value = self.scpi.meas_main()
                after = _sample_clock(t0)

                samples.append(
                    {
                        "host_time_start": before["host_time"],
                        "host_time_end": after["host_time"],
                        "read_elapsed": after["host_perf"] - before["host_perf"],
                        "value": value,
                    }
                )

                if interval > 0.0:
                    remain = before["host_time"] + interval - time.time()
                    if remain > 0.0:
                        time.sleep(remain)

            result = {
                "job_id": job_id,
                "ok": True,
                "stopped": self.stop_event.is_set(),
                "kind": config.kind,
                "range_value": config.range_value,
                "rate": config.rate,
                "duration_requested": duration,
                "stats": _calc_stats([float(x["value"]) for x in samples]),
                "started_at": started_at,
                "finished_at": time.time(),
                "samples": samples,
            }
            self.result_store["continuous"] = result
            if self.stop_event.is_set():
                self.finish("stopped")
            else:
                self.finish("finished")
        except BaseException as exc:
            self.result_store["continuous"] = {
                "job_id": job_id,
                "ok": False,
                "error": repr(exc),
                "traceback": traceback.format_exc(),
            }
            self.fail(exc)

    def handle_start_statistics(
        self,
        req_id,
        args,
    ):
        job_id = args["job_id"]
        duration = float(args["duration"])
        settle = float(args.get("settle", 0.0))

        if duration <= 0.0:
            raise ValueError("duration は正の値でなければならない。")

        config = MeasurementConfig(
            kind=args["kind"],
            range_value=args.get("range_value", "AUTO"),
            rate=args.get("rate", "F"),
        )
        self._apply_meas_config_if_needed(config)

        self.set_running(job_id, "statistics", args)
        self.stop_event.clear()
        self.put_ok(req_id, {"job_id": job_id})

        if settle > 0.0:
            time.sleep(settle)

        started_at = time.time()

        try:
            self.scpi.set_calc_function_average()
            deadline = started_at + duration
            values = []

            while True:
                now = time.time()
                if now >= deadline:
                    break
                if self.stop_event.is_set():
                    break
                values.append(float(self.scpi.meas_main()))

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
                "started_at": started_at,
                "finished_at": time.time(),
                "values": values,
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

    def handle_command(
        self,
        command,
    ):
        """受信 command を振り分けて処理する。"""
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

    def run(
        self,
    ):
        """メインループを実行する。"""
        if not self.open():
            return

        try:
            while True:
                try:
                    command = self.command_q.get()
                    if not self.handle_command(command):
                        break
                except BaseException:
                    try:
                        self.state["worker_loop_error"] = traceback.format_exc()
                    except Exception:
                        pass
        finally:
            self.close()
