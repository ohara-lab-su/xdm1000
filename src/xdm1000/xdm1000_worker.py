#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
XDM1000 の process worker である。

親側の Xdm1000Ctrl は queue、process、state、result を管理する。
この worker は子プロセス内でだけ生成され、Xdm1000Scpi を保持して
SCPI コマンドと長時間測定を実行する。

設計方針
--------
* Python 3.6 互換の書き方だけを使う。
* logger の初期化は cobotta_ctrl の流儀に揃える。
* config が与えられた場合は config 側設定を優先する。
* kind / range_value / rate が現在設定と異なるときだけ設定し直す。
* ctrl / scpi と名前・責務を揃え、meas を使う。
"""

import logging
import math
import time
import traceback

from xdm1000.xdm1000_scpi import Xdm1000Scpi


def _sample_clock(
    t0_perf,
):
    """
    ホスト PC 側の時刻情報を作る。
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
    """
    上位の測定種別名を SCPI の CONFigure 系コマンドへ写像する。
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


def _calc_stats(
    values,
):
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
    """
    子プロセス側で SCPI 実行を担当する worker 実体である。
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
        logger=None,
        log_level=None,
        config=None,
    ):
        """
        worker に必要な共有オブジェクトと接続情報を保持する。
        """
        if logger is None:
            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            logger = logging.getLogger(__name__)

        self._logger = logger
        self._log_level = log_level
        self._config = config

        if config is not None:
            port = getattr(config, "PORT", port)
            timeout = getattr(config, "TIMEOUT", timeout)
            baudrate = getattr(config, "BAUDRATE", baudrate)

        self.command_q = command_q
        self.response_q = response_q
        self.state = state
        self.result_store = result_store
        self.stop_event = stop_event
        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate

        self.scpi = None
        self._current_kind = None
        self._current_range_value = None
        self._current_rate = None

    def set_idle(
        self,
        message="idle",
    ):
        """
        共有 state を idle に戻す。
        """
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

    def finish(
        self,
        message="finished",
    ):
        """
        正常終了状態を state へ反映する。
        """
        self.state["running"] = False
        self.state["job_id"] = None
        self.state["job_type"] = None
        self.state["finished_at"] = time.time()
        self.state["message"] = message

    def fail(
        self,
        exc,
    ):
        """
        失敗状態を state へ反映する。
        """
        self.state["running"] = False
        self.state["finished_at"] = time.time()
        self.state["error"] = repr(exc)
        self.state["traceback"] = traceback.format_exc()
        self.state["message"] = "failed"

    def open(
        self,
    ):
        """
        SCPI 接続を開く。
        """
        try:
            self.scpi = Xdm1000Scpi(
                port=self.port,
                timeout=self.timeout,
                baudrate=self.baudrate,
                logger=self._logger,
                log_level=self._log_level,
                config=self._config,
            )
            self.scpi.remote()
            self.set_idle(message="worker_ready")
            self._current_kind = None
            self._current_range_value = None
            self._current_rate = None
            return True
        except BaseException as exc:
            self.fail(exc)
            return False

    def close(
        self,
    ):
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

    def put_ok(
        self,
        req_id,
        result,
    ):
        """
        正常応答を返す。
        """
        self.response_q.put({"req_id": req_id, "ok": True, "result": result})

    def put_error(
        self,
        req_id,
        exc,
    ):
        """
        例外応答を返す。
        """
        self.response_q.put(
            {
                "req_id": req_id,
                "ok": False,
                "error": repr(exc),
                "traceback": traceback.format_exc(),
            }
        )

    def _get_effective_meas_config(
        self,
        kind=None,
        range_value=None,
        rate=None,
    ):
        """
        None の引数を既存設定または既定値で補完する。
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

    def _apply_config_if_needed(
        self,
        kind,
        range_value,
        rate,
    ):
        """
        必要なときだけ測定条件を装置へ反映する。
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
            _configure_meas(
                self.scpi,
                kind,
                range_value,
            )

        if need_rate:
            self.scpi.set_rate(rate)

        if need_configure or need_rate:
            self._current_kind = kind
            self._current_range_value = range_value
            self._current_rate = rate
            self.state["meas_kind"] = kind
            self.state["range_value"] = range_value
            self.state["rate"] = rate

    def handle_idn(
        self,
        req_id,
    ):
        """
        IDN 取得要求を処理する。
        """
        self.put_ok(req_id, self.scpi.idn())

    def handle_reset(
        self,
        req_id,
    ):
        """
        *RST を実行し、worker 側キャッシュも破棄する。
        """
        self.scpi.reset()
        self._current_kind = None
        self._current_range_value = None
        self._current_rate = None
        self.put_ok(req_id, None)

    def handle_set_meas_mode(
        self,
        req_id,
        args,
    ):
        """
        測定条件設定要求を処理する。
        """
        kind, range_value, rate = self._get_effective_meas_config(
            kind=args.get("kind"),
            range_value=args.get("range_value"),
            rate=args.get("rate"),
        )
        self._apply_config_if_needed(kind, range_value, rate)
        self.put_ok(
            req_id,
            {
                "kind": kind,
                "range_value": range_value,
                "rate": rate,
            },
        )

    def handle_one_shot(
        self,
        req_id,
        args,
    ):
        """
        1 shot 測定要求を処理する。
        """
        kind, range_value, rate = self._get_effective_meas_config(
            kind=args.get("kind"),
            range_value=args.get("range_value"),
            rate=args.get("rate"),
        )
        self._apply_config_if_needed(kind, range_value, rate)

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
                "kind": kind,
                "range_value": range_value,
                "rate": rate,
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
        """
        continuous 測定要求を処理する。
        """
        job_id = args["job_id"]
        duration = float(args["duration"])
        interval = float(args.get("interval", 0.0))
        settle = float(args.get("settle", 0.0))

        if duration <= 0.0:
            raise ValueError("duration は正の値でなければならない。")
        if interval < 0.0:
            raise ValueError("interval は 0 以上でなければならない。")

        kind, range_value, rate = self._get_effective_meas_config(
            kind=args.get("kind"),
            range_value=args.get("range_value"),
            rate=args.get("rate"),
        )
        self._apply_config_if_needed(kind, range_value, rate)

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
                "kind": kind,
                "range_value": range_value,
                "rate": rate,
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
        """
        statistics 測定要求を処理する。
        """
        job_id = args["job_id"]
        duration = float(args["duration"])
        settle = float(args.get("settle", 0.0))

        if duration <= 0.0:
            raise ValueError("duration は正の値でなければならない。")

        kind, range_value, rate = self._get_effective_meas_config(
            kind=args.get("kind"),
            range_value=args.get("range_value"),
            rate=args.get("rate"),
        )
        self._apply_config_if_needed(kind, range_value, rate)

        self.set_running(job_id, "statistics", args)
        self.stop_event.clear()
        self.put_ok(req_id, {"job_id": job_id})

        if settle > 0.0:
            time.sleep(settle)

        started_at = time.time()
        deadline = started_at + duration
        values = []

        try:
            self.scpi.set_calc_function_average()
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
                "kind": kind,
                "range_value": range_value,
                "rate": rate,
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
        """
        1 件の command を処理する。
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

    def run(
        self,
    ):
        """
        worker のメインループである。
        """
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
