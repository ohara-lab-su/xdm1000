#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
XDM1000 の process worker である。

worker は process 使用時の測定実行責務を持つ。
測定条件キャッシュ、continuous/statistics のループ、結果保存を担当する。
SCPI の低レベル送受信は xdm1000_scpi.py に委譲する。
"""

import logging
import time
import traceback

try:
    from x_logger import get_logger
except Exception:
    get_logger = None

from xdm1000.xdm1000_scpi import Xdm1000Scpi


class MeasurementConfig(object):
    """
    現在の測定条件を表す小さな構造体である。
    """

    def __init__(self, kind, range_value="AUTO", rate="F"):
        self.kind = kind
        self.range_value = range_value
        self.rate = rate

    def equals(self, other):
        """
        他の設定と同一かを返す。
        """
        if other is None:
            return False
        if self.kind != other.kind:
            return False
        if self.range_value != other.range_value:
            return False
        if self.rate != other.rate:
            return False
        return True

    def to_dict(self):
        """
        dict へ変換する。
        """
        return {
            "kind": self.kind,
            "range_value": self.range_value,
            "rate": self.rate,
        }


def _sample_clock(t0_perf):
    """
    host 側時刻情報を返す。
    """
    perf = time.perf_counter()
    return {
        "host_time": time.time(),
        "host_perf": perf,
        "t_rel": perf - t0_perf,
    }


def _calc_stats(values):
    """
    値列の基本統計量を返す。
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
    average = sum(values) / float(count)
    variance = sum((x - average) ** 2 for x in values) / float(count)
    return {
        "count": count,
        "minimum": min(values),
        "maximum": max(values),
        "average": average,
        "stdev_population": variance ** 0.5,
    }


def _configure_meas(scpi, kind, range_value="AUTO"):
    """
    測定種別に応じて CONFigure を送る。
    """
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


class _Xdm1000Worker(object):
    """
    子 process 側で SCPI 実行を担当する worker 実体である。
    """

    DEFAULT_CONFIG = MeasurementConfig(
        kind="voltage_dc",
        range_value="AUTO",
        rate="F",
    )

    def __init__(
        self,
        command_q,
        response_q,
        state,
        result_store,
        stop_event,
        port=None,
        timeout=2.0,
        baudrate=115200,
        logger=None,
        log_level=None,
        config=None,
    ):
        """
        worker に必要な共有オブジェクトと接続情報を保持する。
        """
        self.command_q = command_q
        self.response_q = response_q
        self.state = state
        self.result_store = result_store
        self.stop_event = stop_event
        self.config = config

        if config is not None:
            port = getattr(config, "PORT", port)
            timeout = getattr(config, "TIMEOUT", timeout)
            baudrate = getattr(config, "BAUDRATE", baudrate)
            if log_level is None:
                log_level = getattr(config, "LOGGER_LEVEL", log_level)

        if port is None:
            raise ValueError("port が必要である。")

        if logger is None and get_logger is not None:
            logger_name = "xdm1000_worker"
            if config is not None:
                logger_name = getattr(config, "SERVER_LOGGER_NAME", logger_name)
            try:
                logger = get_logger(logger_name, level=log_level)
            except TypeError:
                logger = get_logger(logger_name)
            except Exception:
                logger = None

        if logger is None:
            level_value = getattr(logging, str(log_level or "INFO").upper(), logging.INFO)
            logging.basicConfig(level=level_value)
            logger = logging.getLogger("xdm1000_worker")

        self.logger = logger
        self.log_level = log_level
        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate

        self.scpi = None
        self._current_config = None

    def set_idle(self, message="idle"):
        """
        共有 state を idle に戻す。
        """
        self.state["worker_alive"] = True
        self.state["port"] = self.port
        self.state["baudrate"] = self.baudrate
        self.state["running"] = False
        self.state["job_id"] = None
        self.state["job_type"] = None
        self.state["started_at"] = None
        self.state["finished_at"] = None
        self.state["error"] = None
        self.state["traceback"] = None
        self.state["message"] = message

    def set_running(self, job_id, job_type, args):
        """
        共有 state を running にする。
        """
        self.state["running"] = True
        self.state["job_id"] = job_id
        self.state["job_type"] = job_type
        self.state["started_at"] = time.time()
        self.state["finished_at"] = None
        self.state["error"] = None
        self.state["traceback"] = None
        self.state["message"] = "running"
        self.state["args"] = dict(args)

    def finish(self, message="done"):
        """
        正常終了を state へ反映する。
        """
        self.state["running"] = False
        self.state["job_id"] = None
        self.state["job_type"] = None
        self.state["finished_at"] = time.time()
        self.state["message"] = message

    def fail(self, message, tb):
        """
        失敗状態を state へ反映する。
        """
        self.state["running"] = False
        self.state["finished_at"] = time.time()
        self.state["error"] = message
        self.state["traceback"] = tb
        self.state["message"] = "failed"

    def open(self):
        """
        SCPI 接続を開く。
        """
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
            self.set_idle(message="worker_ready")
            self._current_config = None
            return True
        except Exception:
            self.fail("worker_open_failed", traceback.format_exc())
            return False

    def close(self):
        """
        SCPI 接続を閉じる。
        """
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

    def put_ok(self, req_id, result):
        self.response_q.put({"req_id": req_id, "ok": True, "result": result})

    def put_error(self, req_id, exc):
        self.response_q.put(
            {
                "req_id": req_id,
                "ok": False,
                "error": repr(exc),
                "traceback": traceback.format_exc(),
            }
        )

    def _resolved_config(self, args):
        """
        None 引数を既存設定または既定値で補完する。
        """
        kind = args.get("kind")
        range_value = args.get("range_value")
        rate = args.get("rate")

        base = self._current_config
        if base is None:
            base = self.DEFAULT_CONFIG

        if kind is None:
            kind = base.kind
        if range_value is None:
            range_value = base.range_value
        if rate is None:
            rate = base.rate

        return MeasurementConfig(kind=kind, range_value=range_value, rate=rate)

    def _apply_config_if_needed(self, config):
        """
        必要なときだけ測定条件を装置へ反映する。
        """
        if config.equals(self._current_config):
            return

        if self._current_config is None:
            need_configure = True
            need_rate = True
        else:
            need_configure = (
                self._current_config.kind != config.kind
                or self._current_config.range_value != config.range_value
            )
            need_rate = self._current_config.rate != config.rate

        if need_configure:
            _configure_meas(self.scpi, config.kind, config.range_value)

        if need_rate:
            self.scpi.set_rate(config.rate)

        self._current_config = config
        self.state["meas_kind"] = config.kind
        self.state["range_value"] = config.range_value
        self.state["rate"] = config.rate

    def handle_idn(self, req_id):
        self.put_ok(req_id, self.scpi.idn())

    def handle_reset(self, req_id):
        self.scpi.reset()
        self._current_config = None
        self.put_ok(req_id, None)

    def handle_set_meas_mode(self, req_id, args):
        config = self._resolved_config(args)
        self._apply_config_if_needed(config)
        self.put_ok(req_id, config.to_dict())

    def handle_one_shot(self, req_id, args):
        config = self._resolved_config(args)
        self._apply_config_if_needed(config)

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

    def handle_start_continuous(self, req_id, args):
        job_id = args["job_id"]
        duration = float(args["duration"])
        interval = float(args.get("interval", 0.0))
        settle = float(args.get("settle", 0.0))

        if duration <= 0.0:
            raise ValueError("duration は正の値でなければならない。")
        if interval < 0.0:
            raise ValueError("interval は 0 以上でなければならない。")

        config = self._resolved_config(args)
        self._apply_config_if_needed(config)

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
                "kind": config.kind,
                "range_value": config.range_value,
                "rate": config.rate,
                "duration": duration,
                "interval": interval,
                "requested_stop": bool(self.stop_event.is_set()),
                "host_time_start": started_at,
                "host_time_end": time.time(),
                "count": len(samples),
                "samples": samples,
            }
            result.update(_calc_stats([float(x["value"]) for x in samples]))
            self.result_store["continuous"] = result
            self.finish("continuous_done")
        except Exception:
            self.fail("continuous_failed", traceback.format_exc())

    def handle_start_statistics(self, req_id, args):
        job_id = args["job_id"]
        duration = float(args["duration"])
        settle = float(args.get("settle", 0.0))

        if duration <= 0.0:
            raise ValueError("duration は正の値でなければならない。")

        config = self._resolved_config(args)
        self._apply_config_if_needed(config)

        self.set_running(job_id, "statistics", args)
        self.stop_event.clear()
        self.put_ok(req_id, {"job_id": job_id})

        if settle > 0.0:
            time.sleep(settle)

        started_at = time.time()
        deadline = started_at + duration
        values = []

        try:
            while True:
                now = time.time()
                if now >= deadline:
                    break
                if self.stop_event.is_set():
                    break
                values.append(self.scpi.meas_main())

            result = {
                "job_id": job_id,
                "kind": config.kind,
                "range_value": config.range_value,
                "rate": config.rate,
                "duration": duration,
                "requested_stop": bool(self.stop_event.is_set()),
                "host_time_start": started_at,
                "host_time_end": time.time(),
                "values": values,
            }
            result.update(_calc_stats(values))
            self.result_store["statistics"] = result
            self.finish("statistics_done")
        except Exception:
            self.fail("statistics_failed", traceback.format_exc())

    def handle_command(self, command):
        req_id = command["req_id"]
        name = command["cmd"]
        args = command.get("args", {}) or {}

        try:
            if name == "shutdown":
                self.put_ok(req_id, {"message": "shutdown"})
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
                raise ValueError("未対応の worker command である: {0!r}".format(name))
        except BaseException as exc:
            self.put_error(req_id, exc)
        return True

    def run(self):
        if not self.open():
            return

        try:
            while True:
                try:
                    command = self.command_q.get()
                    if not self.handle_command(command):
                        break
                except (KeyboardInterrupt, EOFError, BrokenPipeError):
                    break
                except BaseException:
                    try:
                        self.state["worker_loop_error"] = traceback.format_exc()
                    except Exception:
                        pass
        finally:
            try:
                self.close()
            except Exception:
                pass
