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
* 同一 ctrl インスタンスの寿命中は worker process を作り直さない。
* ctrl が現在設定の正本を保持し、worker は装置反映済み状態を保持する。
* ``set_meas_mode()`` の内容は、その後の ``meas()`` / ``meas_xxx()`` に引き継ぐ。
* ``meas(パラメータ)`` / ``meas_xxx(パラメータ)`` はその回の指定を優先する。
* config がないときはコンストラクタ引数を使う。
* config とコンストラクタ引数が両方あるときは config を優先する。
* Python 3.6 互換の書き方を使う。
"""

import multiprocessing as mp
import queue
import time
import uuid
from typing import Any, Dict, Optional, Union

from xdm1000.xdm1000_scpi import Xdm1000Scpi
from xdm1000.xdm1000_worker import _Xdm1000Worker


MeasureValue = Union[str, int, float]


class MeasurementConfig(object):
    """
    現在の測定条件を表す小さなデータ構造である。
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

    def to_dict(
        self,
    ):
        return {
            "kind": self.kind,
            "range_value": self.range_value,
            "rate": self.rate,
        }


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
    """
    測定ワーカープロセスの entry point である。
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
    """
    測定器が長時間測定中のため、測定・設定要求を拒否したことを表す。
    """
    pass


class DeviceWorkerError(RuntimeError):
    """
    測定ワーカープロセス側で例外が発生したことを表す。
    """
    pass


class Xdm1000Ctrl(object):
    """
    XDM1000 / XDM1241 を測定器として扱う上位制御クラスである。
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
        XDM1000 上位制御クラスを生成し、必要なら測定ワーカーを起動する。
        """
        # logger は現行流儀を維持する
        if logger is None:
            import logging

            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            logger = logging.getLogger(__name__)

        self.logger = logger
        self.log_level = log_level
        self.config = config
        self.use_process = bool(use_process)

        if config is not None:
            port = getattr(config, "PORT", port)
            timeout = getattr(config, "TIMEOUT", timeout)
            baudrate = getattr(config, "BAUDRATE", baudrate)

        if port is None:
            raise ValueError("port が必要である。")

        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate

        self._current_config = None

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
                    "logger": self.logger,
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
        測定中なら測定・設定 API を拒否する。
        """
        if self._is_running():
            state = self.get_state()
            raise DeviceBusyError(
                "測定器は running 中である: job_type={0}, job_id={1}".format(
                    state.get("job_type"),
                    state.get("job_id"),
                )
            )

    def _resolved_config(
        self,
        kind=None,
        range_value=None,
        rate=None,
    ):
        """
        None の項目を既存設定または既定値で補完した設定を返す。
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

    def _configure_meas_direct_if_needed(
        self,
        config,
    ):
        """
        direct モードで必要なときだけ測定条件を装置へ反映する。
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

    def _cache_config_from_args(
        self,
        args,
    ):
        """
        引数 dict から ctrl 側の現在設定を更新する。
        """
        if args is None:
            return
        self._current_config = self._resolved_config(
            kind=args.get("kind"),
            range_value=args.get("range_value"),
            rate=args.get("rate"),
        )

    def _rpc(
        self,
        name,
        args=None,
        timeout=None,
    ):
        """
        親プロセスから測定ワーカーへ 1 コマンドを送る。
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

                if deadline is not None and remaining <= 0:
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
                    if name in (
                        "set_meas_mode",
                        "one_shot",
                        "start_continuous",
                        "start_statistics",
                    ):
                        self._cache_config_from_args(args)
                    elif name == "reset":
                        self._current_config = None
                    return response.get("result")

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
        """サーバー停止時に呼ばれる解放用エイリアスである。"""
        self.close()

    def get_state(
        self,
    ):
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
        実行中の長時間測定に停止要求を出す。測定中でも呼べる。
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
        連続測定の結果を返す。測定終了後にまとめて取得する想定である。
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

    def idn(
        self,
    ):
        """
        *IDN? を返す。測定中は拒否する。
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
        else:
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
        """
        self._require_not_running()
        config = self._resolved_config(kind, range_value, rate)

        if self.use_process:
            result = self._rpc(
                "set_meas_mode",
                {
                    "kind": config.kind,
                    "range_value": config.range_value,
                    "rate": config.rate,
                },
                timeout=10.0,
            )
        else:
            self._configure_meas_direct_if_needed(config)
            result = config.to_dict()

        self._current_config = config
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

        set_meas_mode() 済みならその設定を引き継ぐ。
        引数が与えられた項目だけ上書きする。
        """
        self._require_not_running()
        config = self._resolved_config(kind, range_value, rate)

        if self.use_process:
            result = self._rpc(
                "one_shot",
                {
                    "kind": config.kind,
                    "range_value": config.range_value,
                    "rate": config.rate,
                    "settle": settle,
                },
                timeout=10.0 + max(0.0, settle),
            )
        else:
            self._configure_meas_direct_if_needed(config)
            if settle > 0.0:
                time.sleep(settle)

            t0 = time.perf_counter()
            before = time.time()
            value = self.scpi.meas_main()
            after = time.time()

            result = {
                "kind": config.kind,
                "range_value": config.range_value,
                "rate": config.rate,
                "value": value,
                "host_time_start": before,
                "host_time_end": after,
                "read_elapsed": time.perf_counter() - t0,
            }

        self._current_config = config
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

        config = self._resolved_config(kind, range_value, rate)

        if self.use_process:
            job_id = uuid.uuid4().hex
            result = self._rpc(
                "start_continuous",
                {
                    "job_id": job_id,
                    "kind": config.kind,
                    "duration": duration,
                    "range_value": config.range_value,
                    "rate": config.rate,
                    "interval": interval,
                    "settle": settle,
                },
                timeout=10.0 + max(0.0, settle),
            )
        else:
            job_id = uuid.uuid4().hex
            self._direct_begin_job(job_id, "continuous")
            self._configure_meas_direct_if_needed(config)

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

        self._current_config = config
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

        config = self._resolved_config(kind, range_value, rate)

        if self.use_process:
            job_id = uuid.uuid4().hex
            result = self._rpc(
                "start_statistics",
                {
                    "job_id": job_id,
                    "kind": config.kind,
                    "duration": duration,
                    "range_value": config.range_value,
                    "rate": config.rate,
                    "settle": settle,
                },
                timeout=10.0 + max(0.0, settle),
            )
        else:
            job_id = uuid.uuid4().hex
            self._direct_begin_job(job_id, "statistics")
            self._configure_meas_direct_if_needed(config)

            if settle > 0.0:
                time.sleep(settle)

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
                average = sum(values) / float(len(values))
                count = len(values)
            else:
                minimum = None
                maximum = None
                average = None
                count = 0

            result = {
                "job_id": job_id,
                "kind": config.kind,
                "range_value": config.range_value,
                "rate": config.rate,
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

        self._current_config = config
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

    process=False と process=True の両方を順に確認できる。
    """
    from xdm1000.config import Config

    config = None
    try:
        config = Config(config_path)
    except Exception:
        config = None

    for use_process in (False, True):
        print("==== use_process = {0} ====".format(use_process))
        dmm = Xdm1000Ctrl(
            port="/dev/cu.usbserial-10",
            timeout=2.0,
            baudrate=115200,
            config=config,
            use_process=use_process,
        )

        try:
            print("初期 state:", dmm.get_state())
            print("IDN:", dmm.idn())
            print(
                dmm.set_meas_mode(
                    kind="voltage_dc",
                    range_value="AUTO",
                    rate="F",
                )
            )
            for _ in range(3):
                print(dmm.meas(settle=0.2))
        finally:
            dmm.close()


if __name__ == "__main__":
    main()
