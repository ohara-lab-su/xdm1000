#!/usr/bin/env python
# coding:utf-8
"""
OWON XDM1000 / XDM1000 用の上位制御クラスである。
"""

import multiprocessing as mp
import queue
import time
import uuid

from xdm1000.config import Config
from xdm1000.xdm1000_worker import _Xdm1000Worker
from xdm1000.xdm1000_worker import MeasurementConfig


def _worker_loop(
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
        XDM1000 上位制御クラスを生成し、必要なら測定ワーカーを起動する。
        logger の初期化は cobotta_ctrl と同じ流儀にする。
        """
        if logger is None:
            import logging

            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            logger = logging.getLogger(__name__)

        self._logger = logger
        self._log_level = log_level
        self._config = config
        self._use_process = use_process

        if config is not None:
            port = getattr(config, "PORT", port)
            timeout = getattr(config, "TIMEOUT", timeout)
            baudrate = getattr(config, "BAUDRATE", baudrate)

        self._port = port
        self._timeout = timeout
        self._baudrate = baudrate

        self._current_config = None

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

    def _is_running(self):
        return bool(self._state.get("running", False))

    def _require_not_running(self):
        if self._is_running():
            raise DeviceBusyError(
                "測定器は running 中である: job_type={0}, job_id={1}".format(
                    self._state.get("job_type"),
                    self._state.get("job_id"),
                )
            )

    def _resolved_config(self, kind=None, range_value=None, rate=None):
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

    def _rpc(self, name, args=None, timeout=None):
        req_id = uuid.uuid4().hex

        with self._rpc_lock:
            self._command_q.put({"req_id": req_id, "cmd": name, "args": args or {}})
            deadline = None if timeout is None else time.time() + timeout

            while True:
                remaining = (
                    None if deadline is None else max(0.0, deadline - time.time())
                )
                if deadline is not None and remaining <= 0:
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
                    if name in ("set_meas_mode", "one_shot"):
                        arg_dict = args or {}
                        self._current_config = self._resolved_config(
                            kind=arg_dict.get("kind"),
                            range_value=arg_dict.get("range_value"),
                            rate=arg_dict.get("rate"),
                        )
                    elif name == "reset":
                        self._current_config = None
                    return response.get("result")

                raise DeviceWorkerError(
                    "{0}\\n{1}".format(
                        response.get("error"),
                        response.get("traceback", ""),
                    )
                )

    def close(self):
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

    def disconnect(self):
        self.close()

    def get_state(self):
        state = dict(self._state)
        state["process_alive"] = self._process.is_alive()
        return state

    def is_running(self):
        return self._is_running()

    def stop_job(self):
        self._stop_event.set()
        return self.get_state()

    def get_continuous_result(self, clear=False):
        result = self._result_store.get("continuous")
        if clear and "continuous" in self._result_store:
            del self._result_store["continuous"]
        return result

    def get_statistics_result(self, clear=False):
        result = self._result_store.get("statistics")
        if clear and "statistics" in self._result_store:
            del self._result_store["statistics"]
        return result

    def idn(self):
        self._require_not_running()
        return self._rpc("idn", timeout=5.0)

    def _reset_scpi_internal(self):
        self._require_not_running()
        self._rpc("reset", timeout=10.0)

    def set_meas_mode(self, kind=None, range_value=None, rate=None):
        self._require_not_running()
        return self._rpc(
            "set_meas_mode",
            {"kind": kind, "range_value": range_value, "rate": rate},
            timeout=10.0,
        )

    def meas_one_shot(self, kind=None, range_value=None, rate=None, settle=0.0):
        self._require_not_running()
        return self._rpc(
            "one_shot",
            {"kind": kind, "range_value": range_value, "rate": rate, "settle": settle},
            timeout=10.0 + max(0.0, settle),
        )

    def meas(self, kind=None, range_value=None, rate=None, settle=0.0):
        return self.meas_one_shot(
            kind=kind,
            range_value=range_value,
            rate=rate,
            settle=settle,
        )

    def meas_voltage_dc(self, range_value=None, rate=None, settle=0.0):
        return self.meas_one_shot("voltage_dc", range_value, rate, settle)

    def meas_current_dc(self, range_value=None, rate=None, settle=0.0):
        return self.meas_one_shot("current_dc", range_value, rate, settle)

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
        kind=None,
        duration=0.0,
        range_value=None,
        rate=None,
        settle=0.0,
    ):
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

    def wait_until_done(self, poll_interval=0.2):
        while True:
            state = self.get_state()
            print("STATE:", state)
            if not state.get("running", False):
                return state
            time.sleep(poll_interval)


def _example_main():
    config = None
    try:
        config = Config("xdm1000_example.yml")
    except Exception:
        config = None

    dmm = Xdm1000Ctrl(
        # port="/dev/cu.usbserial-10",
        # timeout=2.0,
        # baudrate=115200,
        config=config,
    )

    print("初期 state:", dmm.get_state())
    print("IDN:", dmm.idn())

    for i in range(10):
        print("1 shot:")
        print(
            dmm.meas_one_shot(
                kind="voltage_dc",
                range_value="AUTO",
                rate="F",
                settle=0.2,
            )
        )

    dmm.wait_until_done()
    print(dmm.get_statistics_result(clear=True))
    dmm.close()


if __name__ == "__main__":
    _example_main()
