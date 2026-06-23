#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OWON XDM1000 / XDM1241 用の上位制御クラスである。

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
* 長時間測定中は ``running=True`` とし、別の測定・設定 API は拒否する。
* ``get_state()``, ``stop_job()``, ``get_continuous_result()``,
  ``get_statistics_result()`` は測定中でも呼べる。
* Python 3.6 互換の書き方を使う。
"""

import multiprocessing as mp
import queue
import time
import uuid

from xdm1000.config import Config
from xdm1000.xdm1000_scpi import Xdm1000Scpi
from xdm1000.xdm1000_worker import _Xdm1000Worker


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
    """測定ワーカープロセスの entry point である。

    親プロセスとは独立したメモリ空間で実行され、`_Xdm1000Worker` インスタンスを
    生成してメインループを駆動する。このプロセスのみがシリアルポートの占有権を持つ。

    Args:
        command_q (multiprocessing.Queue): 親プロセスからのコマンド要求キュー
        response_q (multiprocessing.Queue): 親プロセスへの応答返却キュー
        state (multiprocessing.managers.DictProxy): プロセス間で共有するステータス辞書
        result_store (multiprocessing.managers.DictProxy): 測定結果を格納する共有辞書
        stop_event (multiprocessing.Event): 長時間測定の停止を要求するイベント
        port (str): シリアルポート パス (例: '/dev/ttyUSB0')
        timeout (float): シリアル通信のタイムアウト秒
        baudrate (int): ボーレート (例: 115200)
        logger (logging.Logger, optional): ロガーインスタンス
        log_level (str, optional): ログレベル文字列
        config (Config, optional): 設定オブジェクト
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
    """測定器が長時間測定中のため、測定・設定要求を拒否したことを表す。

    バックグラウンドで `continuous` または `statistics` ジョブが走行している際に、
    競合する別の設定変更や単発測定要求が発行された場合に送出される。
    """

    pass


class DeviceWorkerError(RuntimeError):
    """測定ワーカープロセス側で例外が発生したことを表す。

    ワーカープロセス内の通信エラーや SCPI コマンドエラーが親プロセスへ
    伝播された際に、元のエラーメッセージとトレースバックを伴って送出される。
    """

    pass


class Xdm1000Ctrl(object):
    """XDM1000 / XDM1241 を測定器として扱う上位制御クラスである。

    `use_process` フラグの切り替えにより、マルチプロセスによる非同期バックグラウンド
    測定モードと、シングルプロセスによるブロッキングダイレクト測定モードを透過的に
    切り替えることができる。
    """

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
        """上位制御クラスを初期化する。

        config があれば config を優先し、無ければコンストラクタ引数を使う。
        `use_process=True` の場合はマネージャ経由で共有オブジェクトおよび
        ワーカープロセスを自動で立ち上げる。

        Args:
            port (str, optional): シリアルポート名
            timeout (float, optional): 通信タイムアウト秒。デフォルトは 2.0 秒
            baudrate (int, optional): ボーレート。デフォルトは 115200
            logger (logging.Logger, optional): 外部ロガー
            log_level (str, optional): ログレベル (例: 'INFO', 'DEBUG')
            config (Config, optional): 設定インスタンス。コンストラクタ引数より優先される
            use_process (bool, optional): ワーカープロセスを使用するかどうか。デフォルトは True
        """
        # XLogger が存在しない時はデフォルトの logging を使う
        if logger is None:
            import logging

            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            logger = logging.getLogger(__name__)

        self.logger = logger
        self.log_level = log_level
        self.config = config
        self.use_process = bool(use_process)

        # Config オブジェクトが存在する場合は属性値を取得し、引数の値を上書きする
        if self.config is not None:
            port = getattr(self.config, "PORT", port)
            timeout = getattr(self.config, "TIMEOUT", timeout)
            baudrate = getattr(self.config, "BAUDRATE", baudrate)

        if port is None:
            raise ValueError("port が必要である。")

        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate

        # 測定器の現在のファンクション・レンジ・サンプリングレートのキャッシュ
        self._current_kind = None
        self._current_range_value = None
        self._current_rate = None

        # use_process=False (ダイレクトモード) 用の内部状態ストア
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

        # 内部リソースの初期化 (モードに応じて必要なオブジェクトのみを有効化する)
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
            # マルチプロセス環境用の共有メモリマネージャおよび同期・通信プリミティブの生成
            self._manager = mp.Manager()
            self._state = self._manager.dict()
            self._result_store = self._manager.dict()
            self._command_q = mp.Queue()
            self._response_q = mp.Queue()
            self._stop_event = mp.Event()
            self._rpc_lock = mp.Lock()

            # 測定バックグラウンドプロセスの初期化と開始
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
                    "logger": None,
                    "log_level": self.log_level,
                    "config": self.config,
                },
                daemon=True,
            )
            self._process.start()

            # ワーカーが正常に初期化を終えて待機状態になるのをブロックして待つ
            self._wait_worker_ready()
        else:
            # ダイレクトモードの場合は自プロセス内で SCPI 低レベル層を生成し、直ちにリモート制御へ移行
            self.scpi = Xdm1000Scpi(
                port=self.port,
                timeout=self.timeout,
                baudrate=self.baudrate,
                logger=self.logger,
                log_level=self.log_level,
                config=self.config,
            )
            self.scpi.remote()

    def _wait_worker_ready(
        self,
        timeout=5.0,
        poll_interval=0.05,
    ):
        """worker 起動完了または起動失敗を待つ。

        親プロセスから呼ばれ、共有メモリ (`self._state`) のメッセージの変化を
        ポーリングして監視する。

        Args:
            timeout (float): 起動完了を待つ最大秒数。デフォルトは 5.0 秒
            poll_interval (float): 状態チェックの間隔秒数。デフォルトは 0.05 秒

        Raises:
            RuntimeError: ワーカープロセスが急死した場合、または初期化中にエラーを検知した場合
            TimeoutError: 制限時間内に 'worker_ready' シグナルが得られなかった場合
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self._process.is_alive():
                raise RuntimeError(
                    "worker process が起動直後に終了した: {0!r}".format(
                        dict(self._state),
                    )
                )

            message = self._state.get("message")
            if message == "worker_ready":
                return

            error = self._state.get("error")
            if error:
                raise RuntimeError(
                    "worker 起動失敗: {0}\n{1}".format(
                        error,
                        self._state.get("traceback", ""),
                    )
                )

            time.sleep(poll_interval)

        raise TimeoutError(
            "worker 起動待ち timeout: {0!r}".format(
                dict(self._state),
            )
        )

    def _is_running(
        self,
    ):
        """長時間測定中かどうかを返す。

        マルチプロセスモードとダイレクトモードの双方において、
        現在バックグラウンドジョブがアクティブであるかをブール値で取得する。

        Returns:
            bool: 測定中であれば True、待機中であれば False
        """
        if self.use_process:
            return bool(self._state.get("running", False))
        return bool(self._direct_state.get("running", False))

    def _require_not_running(
        self,
    ):
        """測定中なら測定・設定 API を拒否する。

        他の測定要求がハードウェア制御と干渉することを防ぐためのガードメソッド。

        Raises:
            DeviceBusyError: 測定器が running 状態のとき
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
        """None の項目を既存設定または既定値で補完して返す。

        ユーザーから引数として明示的に指定されなかった設定項目について、
        現在キャッシュされている状態を引き継ぐための解決処理を行う。

        Args:
            kind (str, optional): 測定種別
            range_value (str/float, optional): レンジ設定値
            rate (str, optional): サンプリングレート

        Returns:
            tuple: (kind, range_value, rate) 各値が補完された 3 要素のタプル
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

    def _cache_config(
        self,
        kind,
        range_value,
        rate,
    ):
        """現在設定キャッシュを更新する。

        Args:
            kind (str): 確定した測定種別
            range_value (str/float): 確定したレンジ設定値
            rate (str): 確定したサンプリングレート
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
        """direct モードで必要なときだけ測定条件を装置へ反映する。

        現在の装置設定キャッシュと比較し、変化がある場合のみ物理的な SCPI コマンドを発行する。
        これにより、不要なオーバーヘッド（通信遅延）を削減する。

        Args:
            kind (str): 適用する測定種別
            range_value (str/float): 適用するレンジ値
            rate (str): 適用するレート速度文字

        Raises:
            ValueError: サポート外の不適切な測定種別が渡された場合
        """
        if (
            self._current_kind == kind
            and self._current_range_value == range_value
            and self._current_rate == rate
        ):
            return

        if kind == "voltage_dc":
            self.scpi.configure_voltage_dc(range_value)
        elif kind == "voltage_ac":
            self.scpi.configure_voltage_ac(range_value)
        elif kind == "current_dc":
            self.scpi.configure_current_dc(range_value)
        elif kind == "current_ac":
            self.scpi.configure_current_ac(range_value)
        elif kind == "resistance":
            self.scpi.configure_resistance(range_value)
        elif kind == "fresistance":
            self.scpi.configure_fresistance(range_value)
        elif kind == "frequency":
            self.scpi.configure_frequency()
        elif kind == "period":
            self.scpi.configure_period()
        elif kind == "capacitance":
            self.scpi.configure_capacitance(range_value)
        elif kind == "temperature_rtd":
            self.scpi.configure_temperature_rtd()
        elif kind == "diode":
            self.scpi.configure_diode()
        elif kind == "continuity":
            self.scpi.configure_continuity()
        else:
            raise ValueError("未対応の測定種別である: {0!r}".format(kind))

        self.scpi.set_rate(rate)
        self._cache_config(kind, range_value, rate)

    def _rpc(
        self,
        name,
        args=None,
        timeout=None,
    ):
        """親プロセスから測定ワーカーへ 1 コマンドを送る。

        引数のシリアライズ、一意なリクエストIDの付与、RPCロックの取得を行い、
        Queueを介したワーカープロセスとの同期型コマンド往復通信をカプセル化する。

        Args:
            name (str): 実行を要求するコマンド名（ワーカー側メソッドに対応）
            args (dict, optional): コマンドに渡す引数マッピング
            timeout (float, optional): 応答待ちのタイムアウト秒数

        Returns:
            any: ワーカープロセス側で正常実行された結果オブジェクト

        Raises:
            RuntimeError: ダイレクトモードで呼んだ場合、または受領IDが不一致の場合
            TimeoutError: 指定時間内にワーカーからの応答が得られなかった場合
            DeviceWorkerError: ワーカー側で例外がキャッチされて返ってきた場合
        """
        if not self.use_process:
            raise RuntimeError("use_process=False では _rpc は使わない。")

        req_id = uuid.uuid4().hex

        with self._rpc_lock:
            # 送信要求をコマンドキューにプッシュ
            self._command_q.put(
                {
                    "req_id": req_id,
                    "cmd": name,
                    "args": args or {},
                }
            )
            if timeout is None:
                deadline = None
            else:
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

                # キューに古い、あるいは他起源の残余メッセージがないかを検証
                if response.get("req_id") != req_id:
                    raise RuntimeError(
                        "worker response の req_id が一致しない: {0!r}".format(
                            response,
                        )
                    )

                if response.get("ok"):
                    # コマンドの正常実行完了に伴い、親プロセス側の内部設定キャッシュを追従させる
                    if name in (
                        "set_meas_mode",
                        "one_shot",
                        "start_continuous",
                        "start_statistics",
                    ):
                        arg_dict = args or {}
                        kind, range_value, rate = self._resolved_config(
                            kind=arg_dict.get("kind"),
                            range_value=arg_dict.get("range_value"),
                            rate=arg_dict.get("rate"),
                        )
                        self._cache_config(kind, range_value, rate)
                    elif name == "reset":
                        self._current_kind = None
                        self._current_range_value = None
                        self._current_rate = None

                    return response.get("result")

                # ワーカー側で何らかのエラーが起きた場合は、親プロセス側でも例外を起こす
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
        """direct モードの長時間測定開始状態を設定する。

        Args:
            job_id (str): ジョブ識別用の一意なID文字列
            job_type (str): 'continuous' または 'statistics' などのジョブ種別
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
        """direct モードの長時間測定終了状態を設定する。"""
        self._direct_state["running"] = False
        self._direct_state["job_id"] = None
        self._direct_state["job_type"] = None
        self._direct_state["finished_at"] = time.time()
        self._direct_stop_requested = False

    def close(
        self,
    ):
        """接続または worker を閉じる。

        リソースの解放リークを防ぐため、プロセスの終了処理（クリーンなシャットダウン、
        および必要に応じた強制ターミネート）、または物理シリアル接続のローカルモードへの
        差し戻しとクローズを安全に実施する。
        """
        if self.use_process:
            if self._process is not None and self._process.is_alive():
                try:
                    self._rpc("shutdown", timeout=2.0)
                except Exception:
                    pass
                self._process.join(timeout=2.0)
                # 猶予期間内に終了しなければ強制停止
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
                    self.scpi.local()  # 測定器の画面制御を本体側へ戻す
                except Exception:
                    pass
                try:
                    self.scpi.close()  # シリアルポートクローズ
                except Exception:
                    pass
                self.scpi = None

    def disconnect(
        self,
    ):
        """close の別名である。"""
        self.close()

    def get_state(
        self,
    ):
        """現在の状態を返す。

        現在の動作モード（プロセス連携か直接通信か）に応じた、最新の内部ステータス
        （実行中のジョブ、エラー情報、通信設定など）をディクショナリ形式で取得する。

        Returns:
            dict: デバイスおよび制御状態を示すステータス情報
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
        """長時間測定中なら True を返す。

        Returns:
            bool: 測定ジョブが実行中であれば True
        """
        return self._is_running()

    def stop_job(
        self,
    ):
        """実行中の長時間測定に停止要求を出す。

        マルチプロセス時は同期イベントフラグをセットし、ダイレクトモード時は
        内部のキャンセルフラグを有効化して、ループ内の次のサンプリングタイミングでの
        脱出を促す。

        Returns:
            dict: 要求を送信した直後の最新のステータス
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
        """連続測定の結果を返す。

        Args:
            clear (bool): 結果の取得後に内部バッファをクリア（削除）するかどうか。デフォルトは False

        Returns:
            dict/None: 格納されている連続測定ジョブの結果データ。存在しない場合は None
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
        """統計モードテストの結果を返す。

        Args:
            clear (bool): 結果の取得後に内部バッファをクリア（削除）するかどうか。デフォルトは False

        Returns:
            dict/None: 最大・最小・平均を含む統計計算結果データ。存在しない場合は None
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
        """*IDN? を返す。

        デバイスの識別情報（メーカー名、モデル名、シリアル番号、ファームウェアバージョン）を取得する。

        Returns:
            str: 測定器から返却された識別文字列
        """
        self._require_not_running()
        if self.use_process:
            return self._rpc("idn", timeout=5.0)
        return self.scpi.idn()

    def _reset_scpi_internal(
        self,
    ):
        """内部確認用に *RST を実行する。

        測定器の設定を工場出荷時、または既定の初期状態へとリセットし、親プロセスが
        管理する設定キャッシュも同様に初期化する。
        """
        self._require_not_running()
        if self.use_process:
            self._rpc("reset", timeout=10.0)
        else:
            self.scpi.reset()
            self._current_kind = None
            self._current_range_value = None
            self._current_rate = None

    def set_meas_mode(
        self,
        kind,
        range_value="AUTO",
        rate="F",
    ):
        """測定種別・レンジ・速度を設定する。

        物理的なデバイスのファンクションをあらかじめ確定させておきたい場合に使用する。

        Args:
            kind (str): 測定種別 (例: 'voltage_dc', 'current_dc', 'resistance')
            range_value (str/float, optional): 測定レンジ指定値。デフォルトは 'AUTO'
            rate (str, optional): サンプリング速度 ('F' (Fast), 'M' (Medium), 'S' (Slow))。デフォルトは 'F'

        Returns:
            dict: 反映された測定設定パラメータの辞書
        """
        self._require_not_running()
        if self.use_process:
            return self._rpc(
                "set_meas_mode",
                {
                    "kind": kind,
                    "range_value": range_value,
                    "rate": rate,
                },
                timeout=10.0,
            )

        self._configure_meas_direct_if_needed(kind, range_value, rate)
        return {
            "kind": kind,
            "range_value": range_value,
            "rate": rate,
        }

    def meas_one_shot(
        self,
        kind=None,
        range_value=None,
        rate=None,
        settle=0.0,
    ):
        """1 shot 測定を実行する。

        単一の最新測定データを取得する。引数が省略された項目については、
        最後に適用された現在設定を引き継ぐ。

        Args:
            kind (str, optional): 測定種別。省略時は現在設定を引き継ぐ
            range_value (str/float, optional): レンジ指定。省略時は現在設定を引き継ぐ
            rate (str, optional): 測定レート。省略時は現在設定を引き継ぐ
            settle (float, optional): コマンド発行直前の安定化待ちスリープ時間（秒）

        Returns:
            dict: 測定値、メタデータ、およびホスト側のタイムスタンプ情報を含む結果辞書
        """
        self._require_not_running()
        kind, range_value, rate = self._resolved_config(
            kind=kind,
            range_value=range_value,
            rate=rate,
        )

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

        # ダイレクトモード時の即時クエリ実行シーケンス
        self._configure_meas_direct_if_needed(kind, range_value, rate)
        if settle > 0.0:
            time.sleep(settle)

        t0 = time.perf_counter()
        before = time.time()
        value = self.scpi.meas_main()  # 実際のシリアルクエリ発行
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
        return result

    def meas(
        self,
        kind=None,
        range_value=None,
        rate=None,
        settle=0.0,
    ):
        """1 shot 測定の短縮名である。

        引数の仕様および戻り値は `meas_one_shot` と完全に等価。
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
        """DC 電圧を 1 shot 測定する。"""
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
        """DC 電流を 1 shot 測定する。"""
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
        """擬似 continuous 測定を開始する。

        指定された期間 (`duration`) 中、一定の間隔 (`interval`) を設けながら
        測定値のサンプリングを繰り返すバックグラウンドタスクまたはループを起動する。

        Args:
            kind (str, optional): 測定種別
            duration (float): 測定を継続する総秒数（正の数値必須）
            range_value (str/float, optional): レンジ
            rate (str, optional): レート
            interval (float): 測定ステップ間の最低インターバルスリープ秒数
            settle (float, optional): ループ突入前の最初の安定化待ち秒数

        Returns:
            dict: 生成されたジョブを管理するための `{"job_id": ...}` 辞書

        Raises:
            ValueError: duration や interval の値が制約を満たさない場合
        """
        self._require_not_running()

        if duration <= 0.0:
            raise ValueError("duration は正の値でなければならない。")
        if interval < 0.0:
            raise ValueError("interval は 0 以上でなければならない。")

        kind, range_value, rate = self._resolved_config(
            kind=kind,
            range_value=range_value,
            rate=rate,
        )

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

        # ダイレクトモード時のメインスレッド内ブロッキングサンプリング
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

            # 指定されたインターバルから測定にかかった実時間を差し引いて正確にウェイトする
            if interval > 0.0:
                remain = before + interval - time.time()
                if remain > 0.0:
                    time.sleep(remain)

        # 結果構造体をビルドしてダイレクトストアへ格納
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
        """statistics モードのテスト測定を開始する。

        指定時間、ハードウェアから最高速度で値を取得し続け、
        その全サンプルの最小・最大・平均値の要約統計量をまとめて集計する。

        Args:
            kind (str, optional): 測定種別
            duration (float): 統計収集を行う総時間（秒）
            range_value (str/float, optional): レンジ
            rate (str, optional): レート
            settle (float, optional): 測定前の待機時間

        Returns:
            dict: 管理用 `{"job_id": ...}` 辞書
        """
        self._require_not_running()

        if duration <= 0.0:
            raise ValueError("duration は正の値でなければならない。")

        kind, range_value, rate = self._resolved_config(
            kind=kind,
            range_value=range_value,
            rate=rate,
        )

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

        # ダイレクトモード時の高頻度サンプリング統計収集
        self._configure_meas_direct_if_needed(kind, range_value, rate)
        job_id = uuid.uuid4().hex
        self._direct_begin_job(job_id, "statistics")

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

        # 配列内の測定値を基に各種記述統計量を算出
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
            "kind": kind,
            "range_value": range_value,
            "rate": rate,
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
        return {"job_id": job_id}

    def wait_until_done(
        self,
        poll_interval=0.2,
    ):
        """running が終わるまで待つ。

        長時間ジョブの終了を呼び出し元スレッドで同期ブロッキング待機したい場合に使用する。
        進捗確認のため、ループ毎に標準出力へ状態をダンプする。

        Args:
            poll_interval (float): 状態を確認するポーリング間隔（秒）。デフォルトは 0.2 秒

        Returns:
            dict: 終了した時点でのデバイスステータス情報
        """
        while True:
            state = self.get_state()
            print("STATE:", state)
            if not state.get("running", False):
                return state
            time.sleep(poll_interval)


def main(
    config_path="xdm1000_example.yml",
):
    """上位制御クラスの動作確認用サンプルである。

    ローカル設定ファイルを読み込み、まずダイレクト通信モードで複数回測定を行った後、
    マルチプロセス非同期通信モードに切り替えて同様の測定シーケンスを実行するデモ。

    Args:
        config_path (str): 読み込む設定ファイルのパス。デフォルトは 'xdm1000_example.yml'
    """
    config = None
    try:
        config = Config(config_path)
    except Exception:
        config = None

    # デフォルトの接続パラメータ（環境に応じてフォールバックされる）
    port = "/dev/cu.usbserial-10"
    timeout = 2.0
    baudrate = 115200

    if config is not None:
        port = getattr(config, "PORT", port)
        timeout = getattr(config, "TIMEOUT", timeout)
        baudrate = getattr(config, "BAUDRATE", baudrate)

    # -------------------------------------------------------------------------
    # テストフェーズ 1: ダイレクトモード (use_process = False)
    # -------------------------------------------------------------------------
    print("==== use_process = False ====")
    dmm = Xdm1000Ctrl(
        # port=port,
        # timeout=timeout,
        # baudrate=baudrate,
        config=config,
        use_process=False,
    )

    print("初期 state:", dmm.get_state())
    print("IDN:", dmm.idn())
    print(
        dmm.set_meas_mode(
            kind="voltage_dc",
            range_value="AUTO",
            rate="F",
        )
    )
    for _ in range(10):
        print(
            dmm.meas(
                settle=0.2,
            )
        )
    dmm.close()

    # -------------------------------------------------------------------------
    # テストフェーズ 2: マルチプロセスモード (use_process = True)
    # -------------------------------------------------------------------------
    print("==== use_process = True ====")
    dmm = Xdm1000Ctrl(
        port=port,
        timeout=timeout,
        baudrate=baudrate,
        config=config,
        use_process=True,
    )

    print("初期 state:", dmm.get_state())
    print("IDN:", dmm.idn())
    print(
        dmm.set_meas_mode(
            kind="voltage_dc",
            range_value="AUTO",
            rate="F",
        )
    )
    for _ in range(10):
        print(
            dmm.meas(
                settle=0.2,
            )
        )
    dmm.close()


if __name__ == "__main__":
    main()
