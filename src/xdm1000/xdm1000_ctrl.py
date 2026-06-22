#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OWON XDM1000 / XDM1241 用の上位制御クラスである。

このファイルは「測定器としての使いやすい API」を提供する上位層である。
SCPI コマンドを直接並べる層ではない。SCPI の低レベル API は
xdm1000_scpi.py に集約する。

設計方針
--------

* Python threading は使わない。
* ``remote()`` / ``local()`` は上位 API として公開しない。
* process を使う場合と使わない場合を選択できる。
* process を使う場合、測定ワーカープロセスだけがシリアルポートを保持する。
* process を使わない場合、ctrl 自身が SCPI を保持して direct 実行する。
* config がないときはコンストラクタ引数を使う。
* config とコンストラクタ引数が両方あるときは config を優先する。
* ``set_meas_mode()`` で現在設定を保持する。
* ``meas()`` / ``meas_xxx()`` は、引数が与えられた項目だけ上書きし、
  与えられない項目は現在設定を引き継ぐ。
* kind / range_value / rate が現在設定と異なるときだけ設定し直す。
* Python 3.6 で動く書き方を使う。
"""

import multiprocessing as mp
import queue
import time
import uuid
from typing import Any, Dict, Optional, Union
import logging

from xdm1000.config import Config
from xdm1000.xdm1000_scpi import Xdm1000Scpi
from xdm1000.xdm1000_worker import _Xdm1000Worker

MeasureValue = Union[str, int, float]


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
    logger_name=None,
    log_level=None,
    config=None,
):
    """測定ワーカープロセスの entry point である。"""
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
        logger_name=logger_name,
        log_level=log_level,
        config=config,
    )
    worker.run()


class DeviceBusyError(RuntimeError):
    """測定器が長時間測定中のため、測定・設定要求を拒否したことを表す。"""
    pass


class DeviceWorkerError(RuntimeError):
    """測定ワーカープロセス側で例外が発生したことを表す。"""
    pass


class Xdm1000Ctrl(object):
    """XDM1000 / XDM1241 を測定器として扱う上位制御クラスである。"""

    def __init__(
        self,
        port=None,
        timeout=2.0,
        baudrate=115200,
        logger=None,
        logger_name=None,
        log_level=None,
        config=None,
        use_process=True,
    ):
        """
        上位制御クラスを初期化する。

        Args:
            port (str): シリアルポート
            timeout (float): シリアル通信タイムアウト
            baudrate (int): 通信速度
            logger: 使用する logger 実体
            logger_name (str): logger 実体が無いときの logger 名
            log_level (str): logging 初期化用レベル
            config: xdm1000.config.Config のインスタンス
            use_process (bool): True のとき worker process を使う
        """
        # XLogger が存在しない時に仕方がないのでデフォルトの logging を使う
        if logger is None:
            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            if logger_name is None:
                logger = logging.getLogger(__name__)
            else:
                logger = logging.getLogger(logger_name)
            # logger = get_silent_logger())

        self._logger = logger
        self._logger_name = logger_name
        self._log_level = log_level
        self._config = config
        self._use_process = use_process

        if config is not None:
            port = getattr(config, "PORT", port)
            timeout = getattr(config, "TIMEOUT", timeout)
            baudrate = getattr(config, "BAUDRATE", baudrate)
            if self._logger_name is None:
                self._logger_name = getattr(config, "SERVER_LOGGER_NAME", None)

        if port is None:
            raise ValueError("port が必要である。")

        self._port = port
        self._timeout = timeout
        self._baudrate = baudrate

        self._current_kind = None
        self._current_range_value = None
        self._current_rate = None

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
                    "logger_name": self._logger_name,
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
                logger_name=self._logger_name,
                log_level=self._log_level,
                config=self._config,
            )
            self._scpi.remote()

    def _is_running(
        self,
    ):
        """
        長時間測定中かどうかを返す。
        """
        if self._use_process:
            return bool(self._state.get("running", False))
        return bool(self._direct_state.get("running", False))

    def _require_not_running(
        self,
    ):
        """
        測定中なら測定・設定 API を拒否する。
        """
        if self._is_running():
            raise DeviceBusyError(
                "測定器は running 中である: job_type={0}, job_id={1}".format(
                    self.get_state().get("job_type"),
                    self.get_state().get("job_id"),
                )
            )

    def _get_effective_meas_config(
        self,
        kind=None,
        range_value=None,
        rate=None,
    ):
        """
        None の項目を現在設定または既定値で補完する。
        """
        if self._current_kind is None:
            current_kind = "voltage_dc"
        else:
            current_kind = self._current_kind

        if self._current_range_value is None:
            current_range_value = "AUTO"
        else:
            current_range_value = self._current_range_value

        if self._current_rate is None:
            current_rate = "F"
        else:
            current_rate = self._current_rate

        if kind is None:
            kind = current_kind
        if range_value is None:
            range_value = current_range_value
        if rate is None:
            rate = current_rate

        return kind, range_value, rate

    def _cache_meas_config(
        self,
        kind,
        range_value,
        rate,
    ):
        """
        現在設定キャッシュを更新する。
        """
        self._current_kind = kind
        self._current_range_value = range_value
        self._current_rate = rate

    def _configure_meas_direct_if_needed(
        self,
        kind,
        range_value,
        rate,
    ):
        """
        direct モードで必要な設定だけを装置へ反映する。
        """
        need_configure = False
        need_rate = False

        if self._current_kind != kind:
            need_configure = True
        if self._current_range_value != range_value:
            need_configure = True
        if self._current_rate != rate:
            need_rate = True

        if need_configure:
            if kind == "voltage_dc":
                self._scpi.configure_voltage_dc(range_value)
            elif kind == "voltage_ac":
                self._scpi.configure_voltage_ac(range_value)
            elif kind == "current_dc":
                self._scpi.configure_current_dc(range_value)
            elif kind == "current_ac":
                self._scpi.configure_current_ac(range_value)
            elif kind == "resistance":
                self._scpi.configure_resistance(range_value)
            elif kind == "fresistance":
                self._scpi.configure_fresistance(range_value)
            elif kind == "frequency":
                self._scpi.configure_frequency()
            elif kind == "period":
                self._scpi.configure_period()
            elif kind == "capacitance":
                self._scpi.configure_capacitance(range_value)
            elif kind == "temperature_rtd":
                self._scpi.configure_temperature_rtd()
            elif kind == "diode":
                self._scpi.configure_diode()
            elif kind == "continuity":
                self._scpi.configure_continuity()
            else:
                raise ValueError("未対応の測定種別である: {0!r}".format(kind))

        if need_rate:
            self._scpi.set_rate(rate)

        if need_configure or need_rate:
            self._cache_meas_config(kind, range_value, rate)

    def _rpc(
        self,
        name,
        args=None,
        timeout=None,
    ):
        """
        親プロセスから測定ワーカーへ 1 コマンドを送る。
        """
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
                        kind, range_value, rate = self._get_effective_meas_config(
                            kind=arg_dict.get("kind"),
                            range_value=arg_dict.get("range_value"),
                            rate=arg_dict.get("rate"),
                        )
                        self._cache_meas_config(kind, range_value, rate)
                    elif name == "reset":
                        self._current_kind = None
                        self._current_range_value = None
                        self._current_rate = None
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

    def disconnect(
        self,
    ):
        """close の別名である。"""
        self.close()

    def get_state(
        self,
    ):
        """
        現在状態を返す。
        """
        if self._use_process:
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
        if self._use_process:
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
        if self._use_process:
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
        if self._use_process:
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
        if self._use_process:
            return self._rpc("idn", timeout=5.0)
        return self._scpi.idn()

    def _reset_scpi_internal(
        self,
    ):
        """
        内部確認用に *RST を実行する。
        """
        self._require_not_running()
        if self._use_process:
            self._rpc("reset", timeout=10.0)
        else:
            self._scpi.reset()
        self._current_kind = None
        self._current_range_value = None
        self._current_rate = None

    def set_meas_mode(
        self,
        kind=None,
        range_value=None,
        rate=None,
    ):
        """
        測定条件を設定する。

        `kind` / `range_value` / `rate` のうち None の項目は現在設定を維持する。
        """
        self._require_not_running()
        kind, range_value, rate = self._get_effective_meas_config(
            kind=kind,
            range_value=range_value,
            rate=rate,
        )

        if self._use_process:
            result = self._rpc(
                "set_meas_mode",
                {"kind": kind, "range_value": range_value, "rate": rate},
                timeout=10.0,
            )
        else:
            self._configure_meas_direct_if_needed(kind, range_value, rate)
            result = {
                "kind": kind,
                "range_value": range_value,
                "rate": rate,
            }

        self._cache_meas_config(kind, range_value, rate)
        return result

    def meas_one_shot(
        self,
        kind=None,
        range_value=None,
        rate=None,
        settle=0.0,
    ):
        """
        1 shot 測定を実行する。

        `set_meas_mode()` 済みならその設定を引き継ぐ。
        `kind` / `range_value` / `rate` が与えられた項目だけ上書きする。
        """
        self._require_not_running()
        kind, range_value, rate = self._get_effective_meas_config(
            kind=kind,
            range_value=range_value,
            rate=rate,
        )

        if self._use_process:
            result = self._rpc(
                "one_shot",
                {
                    "kind": kind,
                    "range_value": range_value,
                    "rate": rate,
                    "settle": settle,
                },
                timeout=10.0 + max(0.0, settle),
            )
        else:
            self._configure_meas_direct_if_needed(kind, range_value, rate)
            if settle > 0.0:
                time.sleep(settle)
            t0 = time.perf_counter()
            before = time.time()
            value = self._scpi.meas_main()
            after = time.time()
            result = {
                "kind": kind,
                "range_value": range_value,
                "rate": rate,
                "value": value,
                "host_time_start": before,
                "host_time_end": after,
                "read_elapsed": time.perf_counter() - t0,
            }

        self._cache_meas_config(kind, range_value, rate)
        return result

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

        kind, range_value, rate = self._get_effective_meas_config(
            kind=kind,
            range_value=range_value,
            rate=rate,
        )

        if self._use_process:
            job_id = uuid.uuid4().hex
            result = self._rpc(
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
        else:
            self._configure_meas_direct_if_needed(kind, range_value, rate)
            job_id = uuid.uuid4().hex
            self._direct_begin_job(job_id, "continuous")

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
                "kind": kind,
                "range_value": range_value,
                "rate": rate,
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

        self._cache_meas_config(kind, range_value, rate)
        return result

    def start_statistics_mode(
        self,
        kind=None,
        duration=0.0,
        range_value=None,
        rate=None,
        settle=0.0,
    ):
        """
        statistics モードのテスト測定を開始する。
        """
        self._require_not_running()

        if duration <= 0.0:
            raise ValueError("duration は正の値でなければならない。")

        kind, range_value, rate = self._get_effective_meas_config(
            kind=kind,
            range_value=range_value,
            rate=rate,
        )

        if self._use_process:
            job_id = uuid.uuid4().hex
            result = self._rpc(
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
        else:
            self._configure_meas_direct_if_needed(kind, range_value, rate)
            job_id = uuid.uuid4().hex
            self._direct_begin_job(job_id, "statistics")

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
                "kind": kind,
                "range_value": range_value,
                "rate": rate,
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

        self._cache_meas_config(kind, range_value, rate)
        return result

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


def main(
    config_path="xdm1000_example.yml",
):
    """
    動作確認用サンプルである。
    """
    config = None
    try:
        config = Config(config_path)
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

        print("set_meas_mode(voltage_dc, AUTO, F)")
        print(
            dmm.set_meas_mode(
                kind="voltage_dc",
                range_value="AUTO",
                rate="F",
            )
        )

        print("meas() x 5")
        for _ in range(5):
            print(
                dmm.meas(
                    settle=0.2,
                )
            )

        print("set_meas_mode(current_dc, AUTO, F)")
        print(
            dmm.set_meas_mode(
                kind="current_dc",
                range_value="AUTO",
                rate="F",
            )
        )

        print("meas(kind='current_dc') x 3")
        for _ in range(3):
            print(
                dmm.meas(
                    kind="current_dc",
                    settle=0.2,
                )
            )

    finally:
        dmm.close()


if __name__ == "__main__":
    main()
