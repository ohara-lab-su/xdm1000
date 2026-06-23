#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""XDM1000 デジタルマルチメータ用 非同期プロセス・ワーカーモジュール。

このモジュールは、OWON XDM1000 ベンチトップ・デジタルマルチメータ（DMM）に対して、
メインプロセスとは独立した子プロセス（マルチプロセス）側で SCPI コマンドの送信や
長時間に及ぶサンプリング測定を安全にバックグラウンド実行するためのワーカーを提供します。

設計・統括方針
--------------
1. 親プロセス（制御側: Xdm1000Ctrl）がコマンドキュー、レスポンスキュー、共有ステート、
   および結果格納領域を一元管理し、本ワーカーは子プロセスのメインループ内で
   シリアル通信インタフェース（Xdm1000Scpi）を独占管理して駆動します。
2. ロギングシステムは、外部（コンストラクタ）からインジェクションされた `logger` を最優先し、
   指定がない場合は標準の `logging` モジュールによる縮退動作を保証します。
3. 装置の測定オーバーヘッドを削減するため、設定（測定種別 / レンジ / レート）が
   現在の内部キャッシュ状態（_device_config）と異なる場合のみ SCPI を再発行します。
4. 本ファイルは Python 3.6+ の環境で動作可能な文法、およびレガシーな `object` 継承
   （新スタイルクラス）の記述様式を厳格に維持します。
"""

import math
import multiprocessing as mp
import time
import traceback
from typing import Any, Optional, Union

# XDM1000 の低レイヤ SCPI コマンドラッパー（別モジュール）をインポート
from xdm1000.xdm1000_scpi import Xdm1000Scpi


class MeasurementConfig(object):
    """ワーカープロセス側で、実際に物理装置へ反映・同期済みの測定条件をキャッシュする不変オブジェクト。

    このクラスは、無駄な SCPI 設定コマンドの二重発行（オーバーヘッド）を検知・スキップするための
    状態比較用エンティティとして機能します。
    """

    def __init__(
        self,
        kind,
        range_value="AUTO",
        rate="F",
    ):
        """MeasurementConfig の初期化。

        Args:
            kind (str): 測定種別 (例: 'voltage_dc', 'current_ac', 'resistance' など)
            range_value (str/float): 測定レンジ。'AUTO' または各測定モードに応じた数値文字列。
            rate (str): サンプリングレート。'F' (Fast), 'M' (Medium), 'S' (Slow) など。
        """
        self.kind = kind
        self.range_value = range_value
        self.rate = rate

    def equals(
        self,
        other,
    ):
        """別インスタンス、または指定された構成情報と現在の設定が「完全一致」するかを判定。

        Args:
            other (MeasurementConfig/None): 比較対象の設定オブジェクト。

        Returns:
            bool: 測定種別、レンジ、レートがすべて一致する場合は True、それ以外は False。
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


def _sample_clock(
    t0_perf,
):
    """ホスト PC 側のシステムクロックおよび高分解能パフォーマンスカウンタを同期取得する。

    測定データのタイムスタンプとして、絶対時刻（UNIX エポックタイム）と、
    測定開始点を基準とした精密な相対経過時間（秒）をペアで生成します。

    Args:
        t0_perf (float): 測定ジョブ全体の開始時点における `time.perf_counter()` の値。

    Returns:
        dict: 以下のキーを持つ時刻情報ディクショナリ。
            - "host_time": `time.time()` によるエポック秒（実時刻同期用）
            - "host_perf": `time.perf_counter()` による高精度計測値
            - "t_rel": ジョブ開始時点からの純粋な相対経過時間（秒）
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
    """上位アプリケーション層の測定種別抽象名を、具体的な SCPI 機器設定関数へマッピングして実行する。

    Args:
        scpi (Xdm1000Scpi): SCPI 通信を行うためのアクティブな機器インスタンス。
        kind (str): 測定種別識別子。
        range_value (str/float, optional): 測定レンジ。デフォルトは "AUTO"。

    Raises:
        ValueError: 定義されていない未知の測定種別名が指定された場合に送出。
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
    """実測値の数値リストから、母集団を対象とした記述統計（基本統計量）を計算する。

    連続サンプリング測定終了時、取得されたデータ全体のサマリーを瞬時に把握するための
    ヘルパー関数です。データが空の場合は安全に初期構造を返します。

    Args:
        values (list of float): 測定から得られた浮動小数点数のリスト。

    Returns:
        dict: 統計算出結果。
            - "count": サンプル数
            - "minimum": 最小値（空なら None）
            - "maximum": 最大値（空なら None）
            - "average": 算術平均（空なら None）
            - "stdev_population": 母標準偏差（空なら None）
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
    # 母分散を計算 (各要素の平均からの偏差の二乗和をデータ数で割る)
    variance = sum((x - average) ** 2 for x in values) / float(count)
    return {
        "count": count,
        "minimum": min(values),
        "maximum": max(values),
        "average": average,
        "stdev_population": math.sqrt(variance),  # 分散の平方根をとって母標準偏差とする
    }


class _Xdm1000Worker(object):
    """マルチプロセス環境下で、子プロセス側のポーリング・SCPI コマンド中継・計測処理を担う実体クラス。

    親プロセスとは `multiprocessing.Queue` および共有メモリ経由で常時通信し、
    ブロックを伴うシリアル通信の入出力処理をメインプロセスから完全に切り離す役割を果たします。
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
        ワーカーが動作するために必要な親プロセス共有オブジェクト、および通信パラメータを初期化・保持。

        Args:
            command_q (mp.Queue): 親プロセスからの指示を格納する入力コマンドキュー。
            response_q (mp.Queue): 同期コマンドに対する応答を親へ返すレスポンスキュー。
            state (mp.managers.DictProxy): プロセスの現在の稼働状態を外部へ公開する共有ディクショナリ。
            result_store (mp.managers.DictProxy): 長時間測定等の大容量結果データを格納する共有リポジトリ。
            stop_event (mp.Event): 長時間測定を途中で緊急停止（ブレイク）させるためのマルチプロセスイベント。
            port (str): シリアル通信の COM ポート名（例: 'COM3', '/dev/ttyUSB0'）。
            timeout (float): シリアル通信のタイムアウト秒数。
            baudrate (int): 通信ボーレート（通常は 115200 など）。
            logger (logging.Logger, optional): 外部提供のロガー。
            log_level (str, optional): ログレベル（例: 'INFO', 'DEBUG'）。
            config (object, optional): 包括的な設定パラメータを保持する構成オブジェクト。
        """
        # XLogger が存在しない時はデフォルトの logging を使う
        if logger is None:
            import logging

            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            logger = logging.getLogger(__name__)

        self.command_q = command_q
        self.response_q = response_q
        self.state = state
        self.result_store = result_store
        self.stop_event = stop_event
        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate
        self.logger = logger
        self.log_level = log_level
        self.config = config
        self.scpi = None  # Xdm1000Scpi の通信インスタンス保持用
        # 装置へ実際に反映済みの MeasurementConfig キャッシュ
        self._device_config = None

        # 汎用 config オブジェクトが存在する場合は、そちらのプロパティ値を通信パラメータとして最優先する
        if self.config is not None:
            self.port = getattr(self.config, "PORT", self.port)
            self.timeout = getattr(self.config, "TIMEOUT", self.timeout)
            self.baudrate = getattr(self.config, "BAUDRATE", self.baudrate)

    def set_idle(
        self,
        message="idle",
    ):
        """
        共有ステートの状態を「アイドル（コマンド待機状態）」に更新し、エラー領域などをクリアする。

        Args:
            message (str): アイドル状態に付随させる詳細なメッセージ文字列。
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
        共有ステートの状態を「実行中」に変更し、現在処理しているジョブのメタデータを注入する。

        Args:
            job_id (str/int): 実行されるタスクの一意の識別子。
            job_type (str): タスクの種類（例: 'continuous', 'statistics'）。
            args (dict): ジョブ起動時に渡された引数パラメータのコピー。
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
        非同期測定ジョブが正常、もしくは意図した停止処理によって完了したことを共有ステートに書き込む。

        Args:
            message (str): 完了時の状態メッセージ（例: 'finished', 'stopped'）。
        """
        self.state["running"] = False
        self.state["finished_at"] = time.time()
        self.state["message"] = message

    def fail(
        self,
        exc,
    ):
        """非同期ジョブ実行中に例外が発生した際、その詳細とトレースバックを共有ステートへ致命的エラーとして記録する。

        Args:
            exc (BaseException): 発生した例外オブジェクト。
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
        SCPI 通信バックエンドを初期化・オープンし、DMM をリモート制御モード（REMOTE）へ移行させる。

        Returns:
            bool: 接続およびリモート移行が成功した場合は True、例外発生時は False。
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
            self.scpi.remote()  # 機器をフロントパネル操作禁止・リモート制御状態にする
            self.state["worker_alive"] = True
            self.state["port"] = self.port
            self.state["baudrate"] = self.baudrate
            self.set_idle("worker_ready")
            return True

        except BaseException as exc:
            # 接続失敗時、生存フラグを落として例外スタックを保持
            self.state["worker_alive"] = False
            self.state["error"] = repr(exc)
            self.state["traceback"] = traceback.format_exc()
            return False

    def close(
        self,
    ):
        """
        DMM の制御権をローカル（LOCAL）に戻し、シリアルポート接続を安全に解放する。
        """
        try:
            if self.scpi is not None:
                try:
                    self.scpi.local()  # フロントパネルの物理操作を有効化
                except Exception:
                    pass  # 切断時の通信エラーは安全のため無視
                self.scpi.close()
        finally:
            self.state["worker_alive"] = False

    def put_ok(
        self,
        req_id,
        result=None,
    ):
        """
        親プロセスに対して、特定の要求（req_id）が正常に完了したことを通知する応答を返す。

        Args:
            req_id (str/int/None): コマンド要求元から渡されたリクエスト識別子。
            result (Any, optional): 応答に添付する処理結果データ。
        """
        self.response_q.put({"req_id": req_id, "ok": True, "result": result})

    def put_error(
        self,
        req_id,
        exc,
    ):
        """
        親プロセスに対して、コマンド処理が失敗した旨と例外内容をキュー経由で即座に返報する。

        Args:
            req_id (str/int/None): コマンド要求元から渡されたリクエスト識別子。
            exc (BaseException): 発生した例外オブジェクト。
        """
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
        kind,
        range_value="AUTO",
        rate="F",
    ):
        """
        指定された測定構成が、直前の設定と異なる場合のみ物理装置に SCPI 命令を送信する。

        連続測定や単発測定が連続するシーンでの、シリアル通信トラフィックと機器の切り替えラグ
        を極小化するためのフィルタリング機構です。

        Args:
            kind (str): 測定種別。
            range_value (str/float): 測定レンジ。
            rate (str): サンプリング速度（F/M/S）。

        Returns:
            MeasurementConfig: 最新の確定済み測定構成オブジェクト。
        """
        config = MeasurementConfig(
            kind=kind,
            range_value=range_value,
            rate=rate,
        )
        # 前回のキャッシュと完全一致すれば、物理機器への SCPI 送信をバイパスする
        if config.equals(self._device_config):
            return config

        # 構成が変化している場合のみ、実際に設定を書き換える
        _configure_meas(self.scpi, kind, range_value)
        self.scpi.set_rate(rate)
        self._device_config = config  # 最新状態をキャッシュへ反映
        return config

    def handle_idn(
        self,
        req_id,
    ):
        """機器識別クエリ `*IDN?` を実行し、製造元、モデル名、シリアル等の情報を親に返す。

        Args:
            req_id (str/int): リクエスト識別子。
        """
        self.put_ok(req_id, self.scpi.idn())

    def handle_reset(
        self,
        req_id,
    ):
        """機器の初期化コマンド `*RST` を発行し、ワーカー内のデバイス構成キャッシュを忘却させる。

        Args:
            req_id (str/int): リクエスト識別子。
        """
        self.scpi.reset()
        self._device_config = None  # キャッシュを破棄し、次回設定を強制同期させる
        self.put_ok(req_id, None)

    def handle_set_meas_mode(
        self,
        req_id,
        args,
    ):
        """測定データの直接取得を行わず、測定設定（種別・レンジ・レート）の先行適用のみを行う。

        Args:
            req_id (str/int): リクエスト識別子。
            args (dict): 'kind', 'range_value', 'rate' を含む指示パラメータ。
        """
        config = self._apply_meas_config_if_needed(
            args["kind"],
            args.get("range_value", "AUTO"),
            args.get("rate", "F"),
        )
        # 外部から常時監視できるよう、パブリックな共有ステート領域にモード情報を反映
        self.state["meas_kind"] = config.kind
        self.state["range_value"] = config.range_value
        self.state["rate"] = config.rate
        self.put_ok(req_id, dict(args))

    def handle_one_shot(
        self,
        req_id,
        args,
    ):
        """単一の測定値をサンプリングして返すワンショット測定命令。

        必要に応じて設定の事前適用、および回路安定化のためのディレイ（settle）を挟んでから
        物理計測を行います。計測前後の高精度ホストタイムスタンプも同時収録します。

        Args:
            req_id (str/int): リクエスト識別子。
            args (dict): 測定構成および安定化時間 'settle' を含むディクショナリ。
        """
        config = self._apply_meas_config_if_needed(
            args["kind"],
            args.get("range_value", "AUTO"),
            args.get("rate", "F"),
        )
        # 指定された回路安定化時間（秒）だけプロセスをスリープ
        time.sleep(float(args.get("settle", 0.0)))

        t0 = time.perf_counter()
        before = _sample_clock(t0)
        value = self.scpi.meas_main()  # 実際の DMM 計測実行
        after = _sample_clock(t0)

        result = {
            "kind": config.kind,
            "range_value": config.range_value,
            "rate": config.rate,
            "value": value,
            "host_time_start": before["host_time"],
            "host_time_end": after["host_time"],
            "read_elapsed": after["host_perf"]
            - before["host_perf"],  # DMM 応答自体の物理所要時間
        }
        self.put_ok(req_id, result)

    def handle_start_continuous(
        self,
        req_id,
        args,
    ):
        """ホスト PC 制御による「擬似連続サンプリング測定」を開始する。

        この関数は長時間にわたってループを占有するため、進捗状況を `self.state` に公開し、
        測定データ一式はレスポンスキューではなく `self.result_store["continuous"]` へ格納します。
        親プロセスから `stop_event` がセットされた場合は、ループの中途であっても即時安全に離脱します。

        Args:
            req_id (str/int): リクエスト識別子（測定開始通知用）。
            args (dict): 必須項目 'job_id', 'duration', 任意項目 'interval', 'settle' など。

        Raises:
            ValueError: 引数の時間パラメータに負数等の異常値が指定された場合。
        """
        job_id = args["job_id"]
        duration = float(args["duration"])
        interval = float(args.get("interval", 0.0))
        if duration <= 0:
            raise ValueError("duration は正の値でなければならない。")
        if interval < 0:
            raise ValueError("interval は 0 以上でなければならない。")

        self.set_running(job_id, "continuous", args)
        self.stop_event.clear()  # 中断フラグを初期化
        config = self._apply_meas_config_if_needed(
            args["kind"],
            args.get("range_value", "AUTO"),
            args.get("rate", "F"),
        )
        time.sleep(float(args.get("settle", 0.0)))

        # 開始に成功した旨を、実測定ループに入る前に親プロセスへ先行応答（ノンブロッキング化のため）
        self.put_ok(req_id, {"job_id": job_id})

        samples = []
        t0 = time.perf_counter()
        deadline = t0 + duration  # 測定を打ち切る絶対的な終了限界時刻
        index = 0

        try:
            while True:
                now = time.perf_counter()
                if now >= deadline:
                    break
                if self.stop_event.is_set():  # 親プロセスからの停止要求を検知
                    break

                before = _sample_clock(t0)
                # DMM からデータを取得
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

                # 指定されたインターバル時間を満たすための精密ウェイト制御（ビジーと 1ms スリープのハイブリッド）
                if interval > 0:
                    next_target = before["host_perf"] + interval
                    while True:
                        remain = next_target - time.perf_counter()
                        if remain <= 0:
                            break
                        # 残り時間が十分あれば OS に処理を戻し(1ms)、直前は極小スピンウェイトで精度を確保
                        time.sleep(min(remain, 0.001))

            # 収集データから基本統計量を算出して結果ディクショナリを構築
            result = {
                "job_id": job_id,
                "ok": True,
                "stopped": self.stop_event.is_set(),
                "kind": config.kind,
                "range_value": config.range_value,
                "rate": config.rate,
                "duration_requested": duration,
                "stats": _calc_stats([float(x["value"]) for x in samples]),
                "started_at": self.state.get("started_at"),
                "finished_at": time.time(),
                "samples": samples,
            }
            self.result_store["continuous"] = result

            if self.stop_event.is_set():
                self.finish("stopped")
            else:
                self.finish("finished")

        except BaseException as exc:
            # ループ内外での予期せぬ通信切断等は、すべてエラーログとして結果領域にダンプ
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
        """DMM の本体内蔵ハードウェア統計機能を用いた試験的測定ジョブ（実証用テストコード）。

        注意：XDM1000 の `CALCulate:AVERage` 系コマンドは、内部的なクリアやバッファ蓄積条件の
        動作詳細が明文化されていない箇所があるため、現段階では厳密な期間統計としては扱わず、
        参考値としてデータを吸い出します。

        Args:
            req_id (str/int): リクエスト識別子。
            args (dict): 'job_id', 'duration' 等を含む制御引数。

        Raises:
            ValueError: duration が 0 以下の場合に送出。
        """
        job_id = args["job_id"]
        duration = float(args["duration"])
        if duration <= 0:
            raise ValueError("duration は正の値でなければならない。")

        self.set_running(job_id, "statistics", args)
        self.stop_event.clear()
        config = self._apply_meas_config_if_needed(
            args["kind"],
            args.get("range_value", "AUTO"),
            args.get("rate", "F"),
        )
        time.sleep(float(args.get("settle", 0.0)))
        self.put_ok(req_id, {"job_id": job_id})

        try:
            # DMM の計算ファンクションを AVERAGE (統計モード) に設定
            self.scpi.set_calc_function_average()
            values = []
            started_at = time.time()
            deadline = started_at + duration

            # 指定時間の間、ホスト側でも値を読み出しつつハードウェア側の蓄積時間を稼ぐ
            while True:
                now = time.time()
                if now >= deadline:
                    break
                if self.stop_event.is_set():
                    break
                values.append(float(self.scpi.meas_main()))

            # DMM 内部の統計バッファから、最小・最大・平均・回数を一括取得
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
        """親プロセスから届いたコマンドディクショナリをパースし、対応する内部ハンドラメソッドへディスパッチする。

        Args:
            command (dict): コマンド指示書。'cmd', 'req_id', 'args' キーを内包する。

        Returns:
            bool: ワーカープロセスのループを継続する場合は True、'shutdown' 命令を受信し終了する場合は False。
        """
        req_id = command.get("req_id")
        name = command.get("cmd")
        args = command.get("args", {})

        try:
            if name == "shutdown":
                # ワーカープロセスの正常終了シグナル。親に了解を返して終了フラグを立てる
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
            # ハンドラ内部から漏れた予期せぬ例外はすべてここでキャッチし、親にエラー応答を戻す
            self.put_error(req_id, exc)

        return True

    def run(
        self,
    ):
        """ワーカープロセスの最上位エントリーポイント（メインループレベル）。

        子プロセスが分岐（fork/spawn）した直後、このメソッドが呼び出され、
        シリアルポートの確立から終了までの全ライフサイクルをハンドリングします。
        """
        if not self.open():
            return  # 初期オープンに失敗した場合は、速やかにプロセスを安全終了させる

        try:
            while True:
                try:
                    # コマンドキューから次の命令が到着するまでブロッキング待機
                    command = self.command_q.get()
                    # 届いたコマンドを処理。shutdown コマンド等の場合はループを離脱
                    if not self.handle_command(command):
                        break
                except BaseException:
                    # キュー取得やハンドリングの致命的なトップレベルエラーをスタック記録
                    self.state["worker_loop_error"] = traceback.format_exc()
        finally:
            # 正常終了・異常終了を問わず、最後は確実にシリアルポートを閉じてローカルモードへ戻す
            self.close()
