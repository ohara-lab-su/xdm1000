#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OWON XDM1000 / XDM1241 用の上位制御クラスである。

この層は direct 実行と process 実行を同じ API で扱う。
低レベル SCPI は xdm1000_scpi.py、process 実行本体は
xdm1000_worker.py に委譲する。

設計方針
--------
* コンストラクタ引数だけでも設定できる。
* config が与えられた場合は config 側を優先する。
* x_logger を基本 logger とする。
* 引数 None は「既存設定を維持する」の意味にする。
* kind / range_value / rate が現在設定と異なるときだけ設定し直す。
* process=False でも direct 実行で meas / continuous / statistics を使える。
* with 構文の利用は前提にしない。
* Python 3.6 以下互換の文法だけを使う。
"""

import multiprocessing as mp
import queue
import time
import uuid

try:
    from x_logger import get_logger
except Exception:
    get_logger = None

from xdm1000.xdm1000_scpi import Xdm1000Scpi
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
    logger_name=None,
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
        logger_name=logger_name,
        log_level=log_level,
        config=config,
    )
    worker.run()


class DeviceBusyError(RuntimeError):
    """長時間測定中の拒否を表す。"""
    pass


class DeviceWorkerError(RuntimeError):
    """worker 側例外を表す。"""
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
        direct または process モードで上位制御クラスを初期化する。

        yml(config) を使わなくてもコンストラクタ引数だけで設定できる。
        config が与えられた場合は config 側を優先する。
        """
        self.use_process = use_process
        self.config = config

        if config is not None:
            port = getattr(config, "PORT", port)
            timeout = getattr(config, "TIMEOUT", timeout)
            baudrate = getattr(config, "BAUDRATE", baudrate)
            if log_level is None:
                log_level = getattr(config, "LOGGER_LEVEL", log_level)

        if port is None:
            raise ValueError("port が必要である。")

        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate
        self.log_level = log_level

        if logger is None and get_logger is not None:
            logger_name = "xdm1000_ctrl"
            if config is not None:
                logger_name = getattr(config, "SERVER_LOGGER_NAME", logger_name)
            try:
                logger = get_logger(logger_name, level=log_level)
            except TypeError:
                logger = get_logger(logger_name)
            except Exception:
                logger = None
        self.logger = logger

        self._current_config = None
        self._direct_result_store = {
            "continuous": None,
            "statistics": None,
        }
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
        self._direct_stop_requested = False

        self.scpi = None
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
                    "port": self.port,
                    "timeout": self.timeout,
                    "baudrate": self.baudrate,
                    "logger_name": None if config is None else getattr(config, "SERVER_LOGGER_NAME", None),
                    "log_level": self.log_level,
                    "config": self.config,
                },
                daemon=True,
            )
            self._process.start()
        else:
            self.scpi = Xdm1000Scpi(
                port=self.port,
                timeout=self.timeout,
                baudrate=self.baudrate,
                logger=self.logger,
                log_level=self.log_level,
                config=self.config,
            )
            self.scpi.remote()

    def _is_running(
        self,
    ):
        """
        長時間測定中かどうかを返す。
        """
        if self.use_process:
            return bool(self._state.get("running", False))
        return bool(self._direct_state.get("running", False))

    def _require_not_running(
        self,
    ):
        """
        長時間測定中なら例外を送出する。
        """
        if self._is_running():
            if self.use_process:
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

    def _resolved_config(
        self,
        kind=None,
        range_value=None,
        rate=None,
    ):
        """
        None 引数を既存設定または既定値で補完する。
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

        return MeasurementConfig(
            kind=kind,
            range_value=range_value,
            rate=rate,
        )

    def _configure_meas_direct(
        self,
        config,
    ):
        """
        direct モードで必要時のみ設定を装置へ反映する。
        """
        if config.equals(self._current_config):
            return

        if config.kind == "voltage_dc":
            self.scpi.configure_voltage_dc(config.range_value)
        elif config.kind == "voltage_ac":
            self.scpi.configure_voltage_ac(config.range_value)
        elif config.kind == "current_dc":
            self.scpi.configure_current_dc(config.range_value)
        elif config.kind == "current_ac":
            self.scpi.configure_current_ac(config.range_value)
        elif config.kind == "resistance":
            self.scpi.configure_resistance(config.range_value)
        elif config.kind == "fresistance":
            self.scpi.configure_fresistance(config.range_value)
        elif config.kind == "frequency":
            self.scpi.configure_frequency()
        elif config.kind == "period":
            self.scpi.configure_period()
        elif config.kind == "capacitance":
            self.scpi.configure_capacitance(config.range_value)
        elif config.kind == "temperature_rtd":
            self.scpi.configure_temperature_rtd()
        elif config.kind == "diode":
            self.scpi.configure_diode()
        elif config.kind == "continuity":
            self.scpi.configure_continuity()
        else:
            raise ValueError("未対応の測定種別である: {0!r}".format(config.kind))

        self.scpi.set_rate(config.rate)
        self._current_config = config

    def _rpc(
        self,
        name,
        args=None,
        timeout=None,
    ):
        """
        process worker へ 1 コマンドを送る。
        """
        if not self.use_process:
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
                        "worker response の req_id が一致しない: {0!r}".format(
                            response
                        )
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

    def _direct_begin_job(
        self,
        job_id,
        job_type,
    ):
        """
        direct モードの長時間測定開始状態を設定する。
        """
        self._direct_state["running"] = True
        self._direct_state["job_id"] = job_id
        self._direct_state["job_type"] = job_type
        self._direct_state["started_at"] = time.time()
        self._direct_state["finished_at"] = None
        self._direct_state["error"] = None
        self._direct_state["traceback"] = None
        self._direct_stop_requested = False

    def _direct_finish_job(
        self,
    ):
        """
        direct モードの長時間測定終了状態を設定する。
        """
        self._direct_state["running"] = False
        self._direct_state["job_id"] = None
        self._direct_state["job_type"] = None
        self._direct_state["finished_at"] = time.time()
        self._direct_stop_requested = False

    def close(
        self,
    ):
        """
        接続または worker を閉じる。
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

    def disconnect(
        self,
    ):
        """
        close の別名である。
        """
        self.close()

    def get_state(
        self,
    ):
        """
        現在状態を返す。
        """
        if self.use_process:
            state = dict(self._state)
            state["process_alive"] = self._process.is_alive()
            return state

        state = dict(self._direct_state)
        state["process_alive"] = False
        return state

    def is_running(
        self,
    ):
        """
        長時間測定中なら True を返す。
        """
        return self._is_running()

    def stop_job(
        self,
    ):
        """
        長時間測定へ停止要求を出す。
        """
        if self.use_process:
            self._stop_event.set()
        else:
            self._direct_stop_requested = True
        return self.get_state()

    def get_continuous_result(
        self,
        clear=False,
    ):
        """
        continuous 結果を返す。
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
        clear=False,
    ):
        """
        statistics 結果を返す。
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

    def idn(
        self,
    ):
        """
        *IDN? を返す。
        """
        self._require_not_running()
        if self.use_process:
            return self._rpc("idn", timeout=5.0)
        return self.scpi.idn()

    def _reset_scpi_internal(
        self,
    ):
        """
        内部確認用に *RST を実行する。
        """
        self._require_not_running()
        if self.use_process:
            self._rpc("reset", timeout=10.0)
            return
        self.scpi.reset()
        self._current_config = None

    def set_meas_mode(
        self,
        kind=None,
        range_value=None,
        rate=None,
    ):
        """
        測定条件を設定する。

        None の項目は既存設定または既定値で補完する。
        既存設定と異なるときだけ実際に装置へ設定を送る。
        """
        self._require_not_running()

        if self.use_process:
            return self._rpc(
                "set_meas_mode",
                {"kind": kind, "range_value": range_value, "rate": rate},
                timeout=10.0,
            )

        config = self._resolved_config(kind, range_value, rate)
        self._configure_meas_direct(config)
        return config.to_dict()

    def meas_one_shot(
        self,
        kind=None,
        range_value=None,
        rate=None,
        settle=0.0,
    ):
        """
        1 shot 測定を実行する。

        None の項目は既存設定または既定値で補完する。
        既存設定と異なるときだけ実際に装置へ設定を送る。
        すでに set_meas_mode 済みで引数を省略した場合はその設定を優先する。
        """
        self._require_not_running()

        if self.use_process:
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
        value = self.scpi.meas_main()
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

    def meas(
        self,
        kind=None,
        range_value=None,
        rate=None,
        settle=0.0,
    ):
        """
        1 shot 測定の短縮名である。
        """
        return self.meas_one_shot(
            kind=kind,
            range_value=range_value,
            rate=rate,
            settle=settle,
        )

    def meas_voltage_dc(
        self,
        range_value=None,
        rate=None,
        settle=0.0,
    ):
        """
        DC 電圧を 1 shot 測定する。
        """
        return self.meas_one_shot(
            kind="voltage_dc",
            range_value=range_value,
            rate=rate,
            settle=settle,
        )

    def meas_current_dc(
        self,
        range_value=None,
        rate=None,
        settle=0.0,
    ):
        """
        DC 電流を 1 shot 測定する。
        """
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
        """
        擬似 continuous 測定を開始する。
        """
        self._require_not_running()

        if duration <= 0.0:
            raise ValueError("duration は正の値でなければならない。")
        if interval < 0.0:
            raise ValueError("interval は 0 以上でなければならない。")

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

            if interval > 0.0:
                remain = before + interval - time.time()
                if remain > 0.0:
                    time.sleep(remain)

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
        """
        statistics テスト測定を開始する。
        """
        self._require_not_running()

        if duration <= 0.0:
            raise ValueError("duration は正の値でなければならない。")

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
            values.append(self.scpi.meas_main())

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

    def wait_until_done(
        self,
        poll_interval=0.2,
    ):
        """
        running が終わるまで待つ。
        """
        while True:
            state = self.get_state()
            if not state.get("running", False):
                return state
            time.sleep(poll_interval)


def _example_main():
    """
    上位制御クラスの動作確認用サンプルである。
    引数は使わず、この関数内の設定だけで動かす。
    config があればそちらを優先する。
    """
    try:
        from xdm1000.config import Config
        cfg = Config()
    except Exception:
        cfg = None

    port = "/dev/cu.usbserial-10"
    timeout = 2.0
    baudrate = 115200
    use_process = True

    mode = "voltage_dc"
    range_value = "AUTO"
    rate = "F"
    settle = 0.2
    duration = 5.0
    interval = 0.0

    dmm = Xdm1000Ctrl(
        port=port,
        timeout=timeout,
        baudrate=baudrate,
        config=cfg,
        use_process=use_process,
    )

    try:
        print("初期 state:", dmm.get_state())
        print("IDN:", dmm.idn())

        dmm.set_meas_mode(
            kind=mode,
            range_value=range_value,
            rate=rate,
        )

        for i in range(10):
            print("1 shot:")
            print(
                dmm.meas(
                    settle=settle,
                )
            )

        # print("continuous start:")
        # print(
        #     dmm.start_continuous_meas(
        #         duration=duration,
        #         interval=interval,
        #         settle=settle,
        #     )
        # )
        # dmm.wait_until_done()
        # print(dmm.get_continuous_result(clear=True))
    finally:
        dmm.close()


if __name__ == "__main__":
    _example_main()
