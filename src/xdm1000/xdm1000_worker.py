#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""XDM1000 デジタルマルチメータ用ワーカープロセス実装である。
K.NAKADA, kengo.nakada@gmail.com

本ファイルは、プロセス分離構成においてシリアルポートと SCPI 実体を保持する
子プロセス側ワーカーを定義する。ctrl 層は利用者向け API とプロセス間通信を
担当し、本ワーカーは command queue から受け取った要求を実機 SCPI 操作へ変換する。

SCPI 層は SCPI コマンドの薄いラッパであり、測定モード、レンジ、測定速度、
連続測定条件などの上位状態は本ワーカー側でキャッシュする。これにより、
親プロセスは直接シリアルポートを保持せずに測定状態と最新結果を参照できる。
"""

import math
import time
import traceback

from xdm1000.xdm1000_scpi import Xdm1000Scpi

# ctrl 層で使う人間可読な mode 名を、XDM1000 の SCPI FUNCtion 引数へ対応付ける。
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
    """上位 API の mode 名を SCPI の FUNCtion パラメータへ変換する。

    Args:
        mode: ctrl 層で指定された測定モード名。

    Returns:
        XDM1000 の FUNCtion コマンドへ渡す SCPI パラメータ文字列。

    Raises:
        ValueError: 未対応の測定モードが指定された場合。
    """
    if mode not in MODE_TO_SCPI_FUNCTION:
        raise ValueError("未対応の測定モードである: {0!r}".format(mode))
    return MODE_TO_SCPI_FUNCTION[mode]


def _validate_integration_speed(speed):
    """XDM1000 の RATE パラメータを検証する。

    Args:
        speed: 測定速度指定。大文字小文字は区別せず、'F', 'M', 'S' のいずれかを受け付ける。

    Returns:
        大文字化した RATE パラメータ文字列。

    Raises:
        ValueError: XDM1000 の RATE として扱えない値が指定された場合。
    """
    speed = str(speed).upper()
    if speed not in ("F", "M", "S"):
        raise ValueError(
            "integration_speed は 'F', 'M', 'S' のいずれかでなければならない。"
        )
    return speed


def _sample_clock(t0_perf):
    """測定時刻をホスト時刻と相対時刻で返す。

    Args:
        t0_perf: 連続測定または単発測定の基準となる ``time.perf_counter()`` 値。

    Returns:
        ``host_time``、``host_perf``、``t_rel`` を持つ dict。
        ``host_time`` は epoch 秒、``host_perf`` は perf_counter 値、
        ``t_rel`` は ``t0_perf`` からの相対秒である。
    """
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

    測定中の中間結果と、終了後の最終結果で同じ構造を返す。親プロセス側の
    ``get_result()`` は、この構造をそのまま参照する。

    Args:
        job_id: 連続測定ジョブの識別子。
        ok: 連続測定が正常系として扱える場合は True。
        stopped: stop 要求により途中停止した場合は True。
        mode: 測定モード名。
        range_value: 手動レンジ値。未設定またはオートレンジ時は None になり得る。
        auto_range: オートレンジ状態。
        integration_speed: RATE 設定値。
        interval: 測定間隔秒。
        duration: 最大測定時間秒。未設定時は None。
        count_limit: 最大サンプル数。未設定時は None。
        samples: 測定サンプル dict の列。
        started_at: 測定開始時刻の epoch 秒。
        finished_at: 測定終了時刻の epoch 秒。測定継続中は None。

    Returns:
        連続測定状態とサンプル列を格納した dict。
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
    """XDM1000 を子プロセス側で制御するワーカーである。

    本クラスは親プロセスから渡される command queue を読み、各 command を
    Xdm1000Scpi の実機操作へ変換する。測定状態は共有 state へ、測定結果は
    共有 result_store へ書き込む。

    Args:
        command_q: 親プロセスからの要求を受け取る queue。
        response_q: 親プロセスへ同期応答を返す queue。
        state: 実行状態を共有する辞書状オブジェクト。
        result_store: 最新測定結果を共有する辞書状オブジェクト。
        stop_event: 連続測定停止要求を受け取るイベント。
        port: シリアルポート名。
        timeout: シリアル通信タイムアウト秒。
        baudrate: シリアル通信ボーレート。
        logger: ロガー。None の場合は標準 logging から生成する。
        log_level: logger 未指定時に用いるログレベル名。
        config: 設定オブジェクト。指定時は PORT、TIMEOUT、BAUDRATE を優先する。
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
        """ワーカーの共有資源、通信条件、測定状態キャッシュを初期化する。

        Args:
            command_q: 親プロセスからの command queue。
            response_q: 親プロセスへの response queue。
            state: worker 状態を書き込む共有辞書。
            result_store: 最新結果を書き込む共有辞書。
            stop_event: 連続測定停止用イベント。
            port: シリアルポート名。
            timeout: シリアル通信タイムアウト秒。
            baudrate: シリアル通信ボーレート。
            logger: 使用するロガー。
            log_level: logger 未指定時のログレベル名。
            config: 設定オブジェクト。指定時は通信条件の既定値を上書きする。
        """
        if logger is None:
            import logging

            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            logger = logging.getLogger(__name__)

        # 親プロセスとの通信・共有状態を保持する。ここには実機 SCPI オブジェクトは置かない。
        self.command_q = command_q
        self.response_q = response_q
        self.state = state
        self.result_store = result_store
        self.stop_event = stop_event

        # シリアル通信条件とログ設定である。config 指定時は後段で上書きされる。
        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate
        self.logger = logger
        self.log_level = log_level
        self.config = config
        self.scpi = None

        # ctrl 層で設定された上位測定条件のキャッシュである。
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
        """共有 state を idle にする。

        Args:
            message: 親プロセスから参照される状態メッセージ。
        """
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
        """共有 state を running にする。

        Args:
            job_id: 実行中ジョブの識別子。
            job_type: ジョブ種別。連続測定では ``"continuous"`` を用いる。
            args: command から受け取った引数 dict。
        """
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
        """共有 state を終了状態にする。

        Args:
            message: 終了理由を表す状態メッセージ。
        """
        self.state["running"] = False
        self.state["finished_at"] = time.time()
        self.state["message"] = message
        self.state["stop_requested"] = False
        self._publish_config_state()

    def fail(self, exc):
        """共有 state にエラーを記録する。

        Args:
            exc: command 処理中または連続測定中に発生した例外。
        """
        self.state["running"] = False
        self.state["finished_at"] = time.time()
        self.state["error"] = repr(exc)
        self.state["traceback"] = traceback.format_exc()
        self.state["message"] = "failed"
        self.state["stop_requested"] = False

    def _publish_config_state(self):
        """現在の設定キャッシュを共有 state に反映する。

        親プロセス側の状態参照 API が、worker 内部の測定条件キャッシュを直接
        読めないため、このメソッドで共有 state へ射影する。
        """
        self.state["mode"] = self._mode
        self.state["range_value"] = self._range_value
        self.state["auto_range"] = self._auto_range
        self.state["integration_speed"] = self._integration_speed
        self.state["continue_interval"] = self._continue_interval
        self.state["continue_duration"] = self._continue_duration
        self.state["continue_count"] = self._continue_count

    def open(self):
        """SCPI 接続を開く。

        Xdm1000Scpi を生成し、装置を remote 状態へ移行する。接続成功時は
        worker_ready として idle 状態を公開する。

        Returns:
            接続成功時は True、初期化失敗時は False。
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
        """SCPI 接続を閉じる。

        可能であれば装置を local 状態へ戻してからシリアル接続を閉じる。
        local 復帰に失敗しても close は継続する。
        """
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
        """正常応答を返す。

        Args:
            req_id: 親プロセスが要求と応答を対応付けるための ID。
            result: command 固有の戻り値。
        """
        self.response_q.put({"req_id": req_id, "ok": True, "result": result})

    def put_error(self, req_id, exc):
        """異常応答を返す。

        Args:
            req_id: 親プロセスが要求と応答を対応付けるための ID。
            exc: command 処理中に発生した例外。
        """
        self.response_q.put(
            {
                "req_id": req_id,
                "ok": False,
                "error": repr(exc),
                "traceback": traceback.format_exc(),
            }
        )

    def _require_mode(self):
        """測定モード設定済みであることを検証する。

        Raises:
            ValueError: 測定モードが未設定の場合。
        """
        if self._mode is None:
            raise ValueError("先に set_mode() で測定モードを設定する必要がある。")

    def handle_idn(self, req_id):
        """*IDN? を返す。

        Args:
            req_id: 親プロセスが要求と応答を対応付けるための ID。
        """
        self.put_ok(req_id, self.scpi.idn())

    def handle_reset(self, req_id):
        """*RST を実行する。

        装置リセット後、worker が保持している測定条件キャッシュと最新測定結果を
        未設定状態へ戻す。

        Args:
            req_id: 親プロセスが要求と応答を対応付けるための ID。
        """
        self.scpi.reset()
        self._mode = None
        self._range_value = None
        self._auto_range = None
        self._integration_speed = None
        self.result_store["result"] = None
        self._publish_config_state()
        self.put_ok(req_id, None)

    def handle_set_mode(self, req_id, args):
        """測定モードを設定する。

        Args:
            req_id: 親プロセスが要求と応答を対応付けるための ID。None の場合は応答しない。
            args: ``mode`` を含む command 引数 dict。
        """
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
        """測定レンジを設定する。

        Args:
            req_id: 親プロセスが要求と応答を対応付けるための ID。
            args: ``range_value`` を含む command 引数 dict。
        """
        range_value = args["range_value"]
        self._require_mode()
        self.scpi.set_range(range_value)
        self._range_value = range_value
        self._auto_range = False
        self._publish_config_state()
        self.put_ok(req_id, {"range_value": range_value})

    def handle_set_auto_range(self, req_id, args):
        """オートレンジを設定する。

        Args:
            req_id: 親プロセスが要求と応答を対応付けるための ID。
            args: ``enabled`` を含む command 引数 dict。

        Raises:
            ValueError: オートレンジを無効化するための手動レンジが未設定の場合。
        """
        enabled = bool(args["enabled"])
        self._require_mode()
        if enabled:
            self.scpi.set_auto_range(True)
            self._auto_range = True
        else:
            if self._range_value is None:
                raise ValueError(
                    "auto_range=False にするには、先に set_range() で手動レンジを設定する必要がある。"
                )
            self.scpi.set_range(self._range_value)
            self._auto_range = False
        self._publish_config_state()
        self.put_ok(req_id, {"auto_range": self._auto_range})

    def handle_set_integration_speed(self, req_id, args):
        """内部測定速度を設定する。

        Args:
            req_id: 親プロセスが要求と応答を対応付けるための ID。
            args: ``speed`` を含む command 引数 dict。
        """
        speed = _validate_integration_speed(args["speed"])
        self.scpi.set_rate(speed)
        self._integration_speed = speed
        self._publish_config_state()
        self.put_ok(req_id, {"integration_speed": speed})

    def handle_set_continue_interval(self, req_id, args):
        """連続測定の測定間隔を設定する。

        Args:
            req_id: 親プロセスが要求と応答を対応付けるための ID。
            args: ``interval`` を含む command 引数 dict。

        Raises:
            ValueError: interval が負の場合。
        """
        interval = float(args["interval"])
        if interval < 0.0:
            raise ValueError("interval は 0 以上でなければならない。")
        self._continue_interval = interval
        self._publish_config_state()
        self.put_ok(req_id, {"continue_interval": interval})

    def handle_set_continue_duration(self, req_id, args):
        """連続測定の最大時間を設定する。

        Args:
            req_id: 親プロセスが要求と応答を対応付けるための ID。
            args: ``duration`` を含む command 引数 dict。None の場合は時間上限を解除する。

        Raises:
            ValueError: duration が正でない場合。
        """
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
        """連続測定の最大回数を設定する。

        Args:
            req_id: 親プロセスが要求と応答を対応付けるための ID。
            args: ``count`` を含む command 引数 dict。None の場合は回数上限を解除する。

        Raises:
            ValueError: count が正の整数でない場合。
        """
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
        """現在設定で 1 回測定する。

        Args:
            req_id: 親プロセスが要求と応答を対応付けるための ID。
            args: 任意で ``wait`` を含む command 引数 dict。
        """
        self._require_mode()
        wait = args.get("wait")
        if wait is not None:
            wait = float(wait)
            if wait > 0.0:
                time.sleep(wait)

        # 読み取り前後のホスト時刻を採取し、通信・装置応答を含む read_elapsed を記録する。
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
        """現在設定で連続測定する。

        測定は worker 内で同期的に実行される。親プロセスには開始直後に job_id を返し、
        測定中は result_store と state を逐次更新する。停止要求は stop_event で受け取る。

        Args:
            req_id: 親プロセスが要求と応答を対応付けるための ID。
            args: ``job_id`` と、任意で ``wait`` を含む command 引数 dict。

        Raises:
            ValueError: duration と count の両方が未設定の場合。
        """
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
            raise ValueError(
                "meas_continue() の前に set_continue_duration() または set_continue_count() を設定する必要がある。"
            )

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
                # stop_event は親プロセスからの非同期停止要求である。
                if self.stop_event.is_set():
                    stopped = True
                    self.state["stop_requested"] = True
                    break

                now = time.perf_counter()
                if deadline is not None and now >= deadline:
                    break
                if count_limit is not None and index >= count_limit:
                    break

                # 1 サンプルごとに読み取り前後の時刻を記録し、測定時間のばらつきを残す。
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

                # 測定中も最新結果を公開する。finished_at=None により running=True になる。
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

                # state には軽量な進捗情報を入れ、result_store にはサンプル列全体を入れる。
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
            # 連続測定中の例外は result_store と state の両方に記録する。
            self.result_store["result"] = {
                "type": "continuous",
                "job_id": job_id,
                "ok": False,
                "error": repr(exc),
                "traceback": traceback.format_exc(),
            }
            self.fail(exc)

    def handle_command(self, command):
        """親プロセスからのコマンドを処理する。

        Args:
            command: ``req_id``、``cmd``、``args`` を持つ command dict。

        Returns:
            worker ループを継続する場合は True、shutdown 要求で終了する場合は False。
        """
        req_id = command.get("req_id")
        name = command.get("cmd")
        args = command.get("args", {})

        try:
            if name == "shutdown":
                self.put_ok(req_id, None)
                return False

            # command 名を handler に分配する。各 handler は SCPI 実行と応答送信を担当する。
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
        """ワーカーメインループを実行する。

        open に成功した場合だけ command queue の読み取りを開始する。shutdown command
        または handle_command が False を返した時点でループを抜け、finally で close する。
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
                    self.state["worker_loop_error"] = traceback.format_exc()
        finally:
            self.close()
