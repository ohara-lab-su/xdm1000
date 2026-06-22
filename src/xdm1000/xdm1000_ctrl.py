#!/usr/bin/env python
# coding:utf-8
"""
OWON XDM1000 / XDM1241 用の上位制御クラスである。

この層は direct 実行と process 実行を同じ API で扱う。
低レベル SCPI は xdm1000_scpi.py、process 実行本体は
xdm1000_worker.py に委譲する。

設計方針
--------
* コンストラクタ引数だけでも設定できる。
* config が与えられた場合は config 側を優先する。
* logger の取り扱いは cobotta_ctrl を参考にして、引数 logger 優先とし、
  無ければ x_logger、さらに無ければ logging を使う。
* kind / range_value / rate の None は「既存設定維持」として扱う。
* kind / range_value / rate が現在設定と異なるときだけ設定し直す。
* process=False でも direct 実行で meas / continuous / statistics を使える。
* ctrl 側に余計な config クラスは作らない。
* with 構文は前提にしない。
* Python 3.5/3.6 互換の文法だけを使う。
"""

import logging
import multiprocessing as mp
import queue
import time
import uuid

try:
    from x_logger import get_logger
except Exception:
    get_logger = None

from xdm1000.config import Config
from xdm1000.xdm1000_scpi import Xdm1000Scpi
from xdm1000.xdm1000_worker import _Xdm1000Worker
from xdm1000.xdm1000_worker import MeasurementConfig


def _worker_loop(
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
    process worker 起動関数である。
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
        logger=logger,
        log_level=log_level,
        config=config,
    )
    worker.run()


class DeviceBusyError(RuntimeError):
    pass


class DeviceWorkerError(RuntimeError):
    pass


class Xdm1000Ctrl(object):
    """
    XDM1000 の上位制御クラスである。
    """

    DEFAULT_CONFIG = MeasurementConfig(
        kind="voltage_dc",
        range_value="AUTO",
        rate="F",
    )

    def __init__(
        self,
        port=None,
        timeout=2.0,
        baudrate=115200,
        logger=None,
        log_level=None,
        config=None,
        use_process=True,
    ):
        """
        direct または process モードで初期化する。

        yml(config) を使わなくてもコンストラクタ引数だけで設定できる。
        config が与えられた場合は config 側を優先する。
        """
        self._config = config
        self._use_process = use_process
        self._log_level = log_level

        if config is not None:
            port = getattr(config, "PORT", port)
            timeout = getattr(config, "TIMEOUT", timeout)
            baudrate = getattr(config, "BAUDRATE", baudrate)
            if self._log_level is None:
                self._log_level = getattr(config, "LOGGER_LEVEL", self._log_level)

        if port is None:
            raise ValueError("port が必要である。")

        if logger is None and get_logger is not None:
            logger_name = "xdm1000_ctrl"
            if config is not None:
                logger_name = getattr(config, "SERVER_LOGGER_NAME", logger_name)
            try:
                logger = get_logger(logger_name, level=self._log_level)
            except TypeError:
                logger = get_logger(logger_name)
            except Exception:
                logger = None

        if logger is None:
            level_value = getattr(logging, str(self._log_level or "INFO").upper(), logging.INFO)
            logging.basicConfig(level=level_value)
            logger = logging.getLogger("xdm1000_ctrl")

        self._logger = logger
        self._port = port
        self._timeout = timeout
        self._baudrate = baudrate

        self._current_config = None
        self._direct_result_store = {
            "continuous": None,
            "statistics": None,
        }
        self._direct_state = {
            "worker_alive": False,
            "port": self._port,
            "baudrate": self._baudrate,
            "running": False,
            "job_id": None,
            "job_type": None,
            "started_at": None,
            "finished_at": None,
            "error": None,
            "traceback": None,
            "message": "direct_scpi_mode",
        }
        self._direct_stop_requested = False

        self._scpi = None
        self._manager = None
        self._state = None
        self._result_store = None
        self._command_q = None
        self._response_q = None
        self._stop_event = None
        self._rpc_lock = None
        self._process = None

        if self._use_process:
            self._manager = mp.Manager()
            self._state = self._manager.dict()
            self._result_store = self._manager.dict()
            self._command_q = mp.Queue()
            self._response_q = mp.Queue()
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
                    "port": self._port,
                    "timeout": self._timeout,
                    "baudrate": self._baudrate,
                    "logger": self._logger,
                    "log_level": self._log_level,
                    "config": self._config,
                },
                daemon=True,
            )
            self._process.start()
        else:
            self._scpi = Xdm1000Scpi(
                port=self._port,
                timeout=self._timeout,
                baudrate=self._baudrate,
                logger=self._logger,
                log_level=self._log_level,
                config=self._config,
            )
            self._scpi.remote()

    def _is_running(self):
        if self._use_process:
            return bool(self._state.get("running", False))
        return bool(self._direct_state.get("running", False))

    def _require_not_running(self):
        if self._is_running():
            if self._use_process:
                job_type = self._state.get("job_type")
                job_id = self._state.get("job_id")
            else:
                job_type = self._direct_state.get("job_type")
                job_id = self._direct_state.get("job_id")
            raise DeviceBusyError(
                "測定器は running 中である: job_type={0}, job_id={1}".format(
                    job_type,
                    job_id,
                )
            )

    def _resolved_config(self, kind=None, range_value=None, rate=None):
        """
        None を既存設定または既定値で補完した設定を返す。
        """
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

    def _configure_meas_direct(self, config):
        """
        direct モードで必要時のみ設定を装置へ反映する。
        """
        if config.equals(self._current_config):
            return

        if config.kind == "voltage_dc":
            self._scpi.configure_voltage_dc(config.range_value)
        elif config.kind == "voltage_ac":
            self._scpi.configure_voltage_ac(config.range_value)
        elif config.kind == "current_dc":
            self._scpi.configure_current_dc(config.range_value)
        elif config.kind == "current_ac":
            self._scpi.configure_current_ac(config.range_value)
        elif config.kind == "resistance":
            self._scpi.configure_resistance(config.range_value)
        elif config.kind == "fresistance":
            self._scpi.configure_fresistance(config.range_value)
        elif config.kind == "frequency":
            self._scpi.configure_frequency()
        elif config.kind == "period":
            self._scpi.configure_period()
        elif config.kind == "capacitance":
            self._scpi.configure_capacitance(config.range_value)
        elif config.kind == "temperature_rtd":
            self._scpi.configure_temperature_rtd()
        elif config.kind == "diode":
            self._scpi.configure_diode()
        elif config.kind == "continuity":
            self._scpi.configure_continuity()
        else:
            raise ValueError("未対応の測定種別である: {0!r}".format(config.kind))

        self._scpi.set_rate(config.rate)
        self._current_config = config

    def _rpc(self, name, args=None, timeout=None):
        if not self._use_process:
            raise RuntimeError("use_process=False では _rpc は使わない。")

        req_id = uuid.uuid4().hex
        with self._rpc_lock:
            self._command_q.put({"req_id": req_id, "cmd": name, "args": args or {}})
            deadline = None
            if timeout is not None:
                deadline = time.time() + timeout

            while True:
                if deadline is None:
                    remaining = None
                else:
                    remaining = max(0.0, deadline - time.time())

                if deadline is not None and remaining <= 0.0:
                    raise TimeoutError("worker 応答待ち timeout: {0!r}".format(name))

                try:
                    response = self._response_q.get(timeout=remaining)
                except queue.Empty:
                    raise TimeoutError("worker 応答待ち timeout: {0!r}".format(name))

                if response.get("req_id") != req_id:
                    raise RuntimeError(
                        "worker response の req_id が一致しない: {0!r}".format(response)
                    )

                if response.get("ok"):
                    result = response.get("result")
                    if name in ("set_meas_mode", "one_shot"):
                        arg_dict = args or {}
                        self._current_config = self._resolved_config(
                            kind=arg_dict.get("kind"),
                            range_value=arg_dict.get("range_value"),
                            rate=arg_dict.get("rate"),
                        )
                    elif name == "reset":
                        self._current_config = None
                    return result

                raise DeviceWorkerError(
                    "{0}\n{1}".format(
                        response.get("error"),
                        response.get("traceback", ""),
                    )
                )

    def _direct_begin_job(self, job_id, job_type):
        self._direct_state["running"] = True
        self._direct_state["job_id"] = job_id
        self._direct_state["job_type"] = job_type
        self._direct_state["started_at"] = time.time()
        self._direct_state["finished_at"] = None
        self._direct_state["error"] = None
        self._direct_state["traceback"] = None
        self._direct_stop_requested = False

    def _direct_finish_job(self):
        self._direct_state["running"] = False
        self._direct_state["job_id"] = None
        self._direct_state["job_type"] = None
        self._direct_state["finished_at"] = time.time()
        self._direct_stop_requested = False

    def close(self):
        if self._use_process:
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
            if self._scpi is not None:
                try:
                    self._scpi.local()
                except Exception:
                    pass
                try:
                    self._scpi.close()
                except Exception:
                    pass
                self._scpi = None

    def disconnect(self):
        self.close()

    def get_state(self):
        if self._use_process:
            state = dict(self._state)
            state["process_alive"] = self._process.is_alive()
            return state

        state = dict(self._direct_state)
        state["process_alive"] = False
        return state

    def is_running(self):
        return self._is_running()

    def stop_job(self):
        if self._use_process:
            self._stop_event.set()
        else:
            self._direct_stop_requested = True
        return self.get_state()

    def get_continuous_result(self, clear=False):
        if self._use_process:
            result = self._result_store.get("continuous")
            if clear and "continuous" in self._result_store:
                del self._result_store["continuous"]
            return result

        result = self._direct_result_store.get("continuous")
        if clear:
            self._direct_result_store["continuous"] = None
        return result

    def get_statistics_result(self, clear=False):
        if self._use_process:
            result = self._result_store.get("statistics")
            if clear and "statistics" in self._result_store:
                del self._result_store["statistics"]
            return result

        result = self._direct_result_store.get("statistics")
        if clear:
            self._direct_result_store["statistics"] = None
        return result

    def idn(self):
        self._require_not_running()
        if self._use_process:
            return self._rpc("idn", timeout=5.0)
        return self._scpi.idn()

    def _reset_scpi_internal(self):
        self._require_not_running()
        if self._use_process:
            self._rpc("reset", timeout=10.0)
            return
        self._scpi.reset()
        self._current_config = None

    def set_meas_mode(self, kind=None, range_value=None, rate=None):
        if self._use_process:
            self._require_not_running()
            return self._rpc(
                "set_meas_mode",
                {"kind": kind, "range_value": range_value, "rate": rate},
                timeout=10.0,
            )

        self._require_not_running()
        config = self._resolved_config(kind, range_value, rate)
        self._configure_meas_direct(config)
        return config.to_dict()

    def meas_one_shot(self, kind=None, range_value=None, rate=None, settle=0.0):
        self._require_not_running()

        if self._use_process:
            return self._rpc(
                "one_shot",
                {
                    "kind": kind,
                    "range_value": range_value,
                    "rate": rate,
                    "settle": settle,
                },
                timeout=10.0 + max(0.0, settle),
            )

        config = self._resolved_config(kind, range_value, rate)
        self._configure_meas_direct(config)
        if settle > 0.0:
            time.sleep(settle)

        t0 = time.perf_counter()
        before = time.time()
        value = self._scpi.meas_main()
        after = time.time()

        return {
            "kind": config.kind,
            "range_value": config.range_value,
            "rate": config.rate,
            "value": value,
            "host_time_start": before,
            "host_time_end": after,
            "read_elapsed": time.perf_counter() - t0,
        }

    def meas(self, kind=None, range_value=None, rate=None, settle=0.0):
        return self.meas_one_shot(
            kind=kind,
            range_value=range_value,
            rate=rate,
            settle=settle,
        )

    def meas_voltage_dc(self, range_value=None, rate=None, settle=0.0):
        return self.meas_one_shot(
            kind="voltage_dc",
            range_value=range_value,
            rate=rate,
            settle=settle,
        )

    def meas_current_dc(self, range_value=None, rate=None, settle=0.0):
        return self.meas_one_shot(
            kind="current_dc",
            range_value=range_value,
            rate=rate,
            settle=settle,
        )

    def start_continuous_meas(
        self,
        kind=None,
        duration=0.0,
        range_value=None,
        rate=None,
        interval=0.0,
        settle=0.0,
    ):
        self._require_not_running()

        if duration <= 0.0:
            raise ValueError("duration は正の値でなければならない。")
        if interval < 0.0:
            raise ValueError("interval は 0 以上でなければならない。")

        if self._use_process:
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

        job_id = uuid.uuid4().hex
        config = self._resolved_config(kind, range_value, rate)
        self._direct_begin_job(job_id, "continuous")
        self._configure_meas_direct(config)

        if settle > 0.0:
            time.sleep(settle)

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
            value = self._scpi.meas_main()
            after = time.time()

            samples.append(
                {
                    "host_time_start": before,
                    "host_time_end": after,
                    "read_elapsed": time.perf_counter() - t0,
                    "value": value,
                }
            )

            if interval > 0.0:
                remain = before + interval - time.time()
                if remain > 0.0:
                    time.sleep(remain)

        values = [float(x["value"]) for x in samples]
        result = {
            "job_id": job_id,
            "kind": config.kind,
            "range_value": config.range_value,
            "rate": config.rate,
            "duration": duration,
            "interval": interval,
            "requested_stop": bool(self._direct_stop_requested),
            "host_time_start": started_at,
            "host_time_end": time.time(),
            "count": len(samples),
            "samples": samples,
        }
        if values:
            result["minimum"] = min(values)
            result["maximum"] = max(values)
            result["average"] = sum(values) / float(len(values))
        else:
            result["minimum"] = None
            result["maximum"] = None
            result["average"] = None

        self._direct_result_store["continuous"] = result
        self._direct_finish_job()
        return {"job_id": job_id}

    def start_statistics_mode(
        self,
        kind=None,
        duration=0.0,
        range_value=None,
        rate=None,
        settle=0.0,
    ):
        self._require_not_running()

        if duration <= 0.0:
            raise ValueError("duration は正の値でなければならない。")

        if self._use_process:
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

        job_id = uuid.uuid4().hex
        config = self._resolved_config(kind, range_value, rate)
        self._direct_begin_job(job_id, "statistics")
        self._configure_meas_direct(config)

        if settle > 0.0:
            time.sleep(settle)

        started_at = time.time()
        deadline = started_at + duration
        values = []

        while True:
            now = time.time()
            if now >= deadline:
                break
            if self._direct_stop_requested:
                break
            values.append(self._scpi.meas_main())

        count = len(values)
        if count > 0:
            minimum = min(values)
            maximum = max(values)
            average = sum(values) / float(count)
        else:
            minimum = None
            maximum = None
            average = None

        result = {
            "job_id": job_id,
            "kind": config.kind,
            "range_value": config.range_value,
            "rate": config.rate,
            "duration": duration,
            "requested_stop": bool(self._direct_stop_requested),
            "host_time_start": started_at,
            "host_time_end": time.time(),
            "count": count,
            "minimum": minimum,
            "maximum": maximum,
            "average": average,
            "values": values,
        }
        self._direct_result_store["statistics"] = result
        self._direct_finish_job()
        return {"job_id": job_id}

    def wait_until_done(self, poll_interval=0.2):
        while True:
            state = self.get_state()
            if not state.get("running", False):
                return state
            time.sleep(poll_interval)


def _example_main():
    """
    動作確認用サンプルである。

    引数処理は使わない。
    config yml を使う場合は xdm1000_example.yml を読む。
    """
    config = None
    try:
        config = Config("xdm1000_example.yml")
    except Exception:
        config = None

    dmm = Xdm1000Ctrl(
        port="/dev/cu.usbserial-10",
        timeout=2.0,
        baudrate=115200,
        config=config,
        use_process=True,
    )

    try:
        print("初期 state:", dmm.get_state())
        print("IDN:", dmm.idn())

        dmm.set_meas_mode(
            kind="voltage_dc",
            range_value="AUTO",
            rate="F",
        )

        for i in range(5):
            print(dmm.meas(settle=0.2))

    finally:
        dmm.close()


if __name__ == "__main__":
    _example_main()
