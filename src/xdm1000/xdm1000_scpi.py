#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OWON XDM1241 / XDM1000 系デジタルマルチメータ用 SCPI ラッパである。

このファイルは pyserial 経由で USB-Serial 接続された XDM1241 に SCPI を送る。
XDM1041 / XDM2041 用として公開されている XDM1000 Series Programming Manual に
記載された SCPI コマンドを一通り薄く包む。

設計方針
--------

* 低レベル SCPI の送受信だけを担当する。
* config がないときはコンストラクタ引数を使う。
* config とコンストラクタ引数が両方あるときは config を優先する。
* logger 実体が無いときだけ x_logger / logging を使う。
* pyserial.Serial() の引数は型を明示して、型エラーが出にくいようにする。
* Python 3.6 で動く書き方を使う。
"""

import time
import serial


class AverageStats(object):
    """CALCulate:AVERage:ALL? の結果を保持するクラスである。

    測定器から取得した統計情報（最小値、最大値、平均値、サンプル数）を
    構造化してカプセル化する。
    """

    def __init__(
        self,
        minimum,
        maximum,
        average,
        count,
    ):
        """統計データオブジェクトを初期化する。

        Args:
            minimum (float): 測定データの最小値
            maximum (float): 測定データの最大値
            average (float): 測定データの平均値
            count (int): 統計計算に含まれる測定サンプル総数
        """
        self.minimum = minimum
        self.maximum = maximum
        self.average = average
        self.count = count


class Xdm1000Scpi(object):
    """OWON XDM1241 に SCPI コマンドを送る低レベル制御クラスである。

    pyserial を内包し、テキストベースの SCPI コマンドの送信、および
    クエリに対する応答文字列の受信と基本的な型変換（キャスト）を担当する。
    """

    def __init__(
        self,
        port=None,
        timeout=1.0,
        baudrate=115200,
        logger=None,
        # logger_name=None,
        log_level=None,
        config=None,
    ):
        """USB-Serial ポートを開く。

        config が提供されている場合はそこから通信パラメータおよびログレベルを抽出し、
        引数で渡されたパラメータよりも優先して適用する。

        Args:
            port (str/None): シリアルポート名 (例: '/dev/ttyUSB0', 'COM3')
            timeout (float, optional): 通信のタイムアウト秒。デフォルトは 1.0 秒
            baudrate (int, optional): ボーレート。デフォルトは 115200
            logger (logging.Logger, optional): 外部から注入されるロガーインスタンス
            log_level (str, optional): ログレベル文字列 (例: 'DEBUG', 'INFO')
            config (Config, optional): 各種設定値を保持するConfigオブジェクト

        Raises:
            ValueError: 最終的にシリアルポート (port) が指定されなかった場合
        """
        # XLogger が存在しない時はデフォルトの logging を使う
        if logger is None:
            import logging

            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            logger = logging.getLogger(__name__)

        # Config オブジェクトから値を優先的に解決
        if config is not None:
            port = getattr(config, "PORT", port)
            timeout = getattr(config, "TIMEOUT", timeout)
            baudrate = getattr(config, "BAUDRATE", baudrate)

            if log_level is None:
                log_level = getattr(config, "LOGGER_LEVEL", log_level)

        self._logger = logger
        self._config = config

        if port is None:
            raise ValueError("port が必要である。")

        # 厳密な型エラーを防ぐため明示的にキャスト
        self._port = str(port)
        self._timeout = float(timeout)
        self._baudrate = int(baudrate)

        # 測定器仕様に合わせたシリアル通信仕様 (8-N-1、フロー制御なし) でポートを開く
        self.ser = serial.Serial(
            port=self._port,
            baudrate=int(self._baudrate),
            bytesize=int(serial.EIGHTBITS),
            parity=str(serial.PARITY_NONE),
            stopbits=int(serial.STOPBITS_ONE),
            timeout=float(self._timeout),
            write_timeout=float(self._timeout),
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )

    def close(
        self,
    ):
        """シリアルポートを閉じる。

        ポートが開いている場合のみ閉じ、リソースのリークを防止する。
        """
        if self.ser is not None and self.ser.is_open:
            self.ser.close()

    def disconnect(
        self,
    ):
        """サーバー停止時に呼ばれる解放用エイリアスである。

        ``close()`` と同様の処理を行う。
        """
        self.close()

    def __del__(
        self,
    ):
        """オブジェクト破棄時に local mode へ戻して解放する。

        デストラクタにより、プログラム終了時やインスタンス破棄時に自動的に
        測定器の制御権を本体パネル側に戻し、シリアルポートを安全にクローズする。
        """
        try:
            self.local()
        except Exception:
            pass

        try:
            self.close()
        except Exception:
            pass

    def write(
        self,
        command,
    ):
        """SCPI コマンドを送信する。

        末尾に改行コード LF (\\n) が付加されていない場合は自動で補完し、
        ASCII エンコードを施してシリアルバスへフラッシュする。

        Args:
            command (str): 測定器へ送信する SCPI コマンド文字列
        """
        if not command.endswith("\n"):
            command += "\n"
        try:
            self._logger.debug("SCPI WRITE: %s", command.rstrip())
        except Exception:
            pass
        self.ser.write(command.encode("ascii"))
        self.ser.flush()

    def query(
        self,
        command,
    ):
        """SCPI クエリを送信し、1 行の応答文字列を返す。

        古い受信残余データとの混同を防ぐため、コマンド発行前に受信バッファをクリアする。
        コマンド送信後、改行コードに到達するかタイムアウトするまで応答を読み出す。

        Args:
            command (str): 疑問符 (?) で終わる SCPI クエリ文字列

        Returns:
            str: 測定器から返ってきた、左右の空白や改行を取り除いた応答文字列

        Raises:
            TimeoutError: 測定器からのレスポンスが空（タイムアウト）だった場合
        """
        self.ser.reset_input_buffer()  # 受信バッファをクリアして同期を担保
        self.write(command)
        response = self.ser.readline().decode("ascii", errors="replace").strip()
        if response == "":
            raise TimeoutError("no response from XDM1241: {0}".format(command))
        try:
            self._logger.debug("SCPI READ : %s", response)
        except Exception:
            pass
        return response

    def query_float(
        self,
        command,
    ):
        """SCPI クエリ応答を float として返す。

        Args:
            command (str): SCPI クエリ文字列

        Returns:
            float: 浮動小数点数に変換された応答値
        """
        return float(self.query(command))

    def query_int(
        self,
        command,
    ):
        """SCPI クエリ応答を int として返す。

        実数表記（例: "1.0"）で返ってきた場合でも安全に変換できるよう、
        一度 float を経由してから整数へキャストする。

        Args:
            command (str): SCPI クエリ文字列

        Returns:
            int: 整数に変換された応答値
        """
        return int(float(self.query(command)))

    def idn(
        self,
    ):
        """*IDN? により機器識別文字列を取得する。

        Returns:
            str: 機器の製造元、モデル名、シリアル、バージョン情報を含む文字列
        """
        return self.query("*IDN?")

    def reset(
        self,
    ):
        """*RST により機器設定をデフォルトに戻す。"""
        self.write("*RST")

    def remote(
        self,
    ):
        """SYSTem:REMote により SCPI remote mode に入る。

        これにより、フロントパネルの操作がロックされ上位 PC からの制御を受け付ける。
        """
        self.write("SYSTem:REMote")

    def local(
        self,
    ):
        """SYSTem:LOCal により SCPI mode を終了し、ローカル操作へ戻す。

        これにより、フロントパネルの物理ボタン操作が再び有効化される。
        """
        self.write("SYSTem:LOCal")

    def set_beeper(
        self,
        enabled,
    ):
        """ブザーの ON/OFF を設定する。

        Args:
            enabled (bool): True でブザー有効 (ON)、False で無効 (OFF)
        """
        if enabled:
            self.write("SYSTem:BEEPer:STATe ON")
        else:
            self.write("SYSTem:BEEPer:STATe OFF")

    def get_beeper(
        self,
    ):
        """ブザー状態を取得する。True が ON、False が OFF である。

        Returns:
            bool: ブザー設定の状態
        """
        return self.query_int("SYSTem:BEEPer:STATe?") != 0

    def configure_voltage_dc(
        self,
        range_value="AUTO",
    ):
        """直流電圧測定 (DCV) のファンクションおよびレンジを設定する。

        Args:
            range_value (str/float): レンジ指定値 (例: 'AUTO', 5, 50)
        """
        self.write("CONFigure:VOLTage:DC {0}".format(range_value))

    def configure_voltage_ac(
        self,
        range_value="AUTO",
    ):
        """交流電圧測定 (ACV) のファンクションおよびレンジを設定する。

        Args:
            range_value (str/float): レンジ指定値
        """
        self.write("CONFigure:VOLTage:AC {0}".format(range_value))

    def configure_current_dc(
        self,
        range_value="AUTO",
    ):
        """直流電流測定 (DCI) のファンクションおよびレンジを設定する。

        Args:
            range_value (str/float): レンジ指定値
        """
        self.write("CONFigure:CURRent:DC {0}".format(range_value))

    def configure_current_ac(
        self,
        range_value="AUTO",
    ):
        """交流電流測定 (ACI) のファンクションおよびレンジを設定する。

        Args:
            range_value (str/float): レンジ指定値
        """
        self.write("CONFigure:CURRent:AC {0}".format(range_value))

    def configure_resistance(
        self,
        range_value="AUTO",
    ):
        """2線式抵抗測定 (RES) のファンクションおよびレンジを設定する。

        Args:
            range_value (str/float): レンジ指定値
        """
        self.write("CONFigure:RESistance {0}".format(range_value))

    def configure_fresistance(
        self,
        range_value="AUTO",
    ):
        """4線式抵抗測定 (FRES) のファンクションおよびレンジを設定する。

        Args:
            range_value (str/float): レンジ指定値
        """
        self.write("CONFigure:FRESistance {0}".format(range_value))

    def configure_frequency(
        self,
    ):
        """周波数測定 (FREQ) のファンクションを設定する。"""
        self.write("CONFigure:FREQuency")

    def configure_period(
        self,
    ):
        """周期測定 (PER) のファンクションを設定する。"""
        self.write("CONFigure:PERiod")

    def configure_capacitance(
        self,
        range_value="AUTO",
    ):
        """静電容量測定 (CAP) のファンクションおよびレンジを設定する。

        Args:
            range_value (str/float): レンジ指定値
        """
        self.write("CONFigure:CAPacitance {0}".format(range_value))

    def configure_temperature_rtd(
        self,
    ):
        """RTD 温度測定 (TEMP) のファンクションを設定する。"""
        self.write("CONFigure:TEMPerature:RTD")

    def configure_diode(
        self,
    ):
        """ダイオードテスト のファンクションを設定する。"""
        self.write("CONFigure:DIODe")

    def configure_continuity(
        self,
    ):
        """導通テスト のファンクションを設定する。"""
        self.write("CONFigure:CONTinuity")

    def set_function(
        self,
        function,
        display=1,
    ):
        """SENSe:FUNCtion により測定機能を選択する。

        Args:
            function (str): SCPI の測定機能名。例: 'VOLT', 'VOLT AC', 'CURR', 'RES'
            display (int): 表示番号。1 は主表示、2 は副表示。デフォルトは 1。
        """
        if int(display) == 1:
            self.write('FUNCtion "{0}"'.format(function))
        elif int(display) == 2:
            self.write('FUNCtion2 "{0}"'.format(function))
        else:
            raise ValueError("display は 1 または 2 でなければならない。")

    def get_function(
        self,
        display=1,
    ):
        """SENSe:FUNCtion? により現在の測定機能を取得する。

        Args:
            display (int): 表示番号。1 は主表示、2 は副表示。

        Returns:
            str: 測定器が返す測定機能文字列
        """
        if int(display) == 1:
            return self.query("FUNCtion?")
        if int(display) == 2:
            return self.query("FUNCtion2?")
        raise ValueError("display は 1 または 2 でなければならない。")

    def set_range(
        self,
        range_value,
    ):
        """RANGE により現在の測定機能のレンジを設定する。

        Args:
            range_value (str/int/float): RANGE に渡す値。例: 1, 2, 'DEF'
        """
        self.write("RANGE {0}".format(range_value))

    def set_auto_range(
        self,
        enabled=True,
    ):
        """AUTO によりオートレンジを有効化する。

        XDM1000 の Programming Manual では AUTO は有効化コマンドであり、
        OFF パラメータ付きの汎用 AUTO OFF は定義されていない。False を指定した場合、
        明示的なレンジは set_range() で設定する。

        Args:
            enabled (bool): True の場合のみ AUTO を送る。

        Raises:
            ValueError: False が指定された場合。
        """
        if bool(enabled):
            self.write("AUTO")
            return
        raise ValueError(
            "AUTO OFF は汎用 SCPI として定義されていない。手動レンジは set_range() を使う。"
        )

    def get_auto_range(
        self,
    ):
        """AUTO? によりオートレンジ状態を取得する。

        Returns:
            bool: オートレンジ有効なら True。
        """
        return self.query_int("AUTO?") != 0

    def set_calc_function_average(
        self,
    ):
        """統計計算機能 (AVERage) を有効化する。"""
        self.write("CALCulate:FUNCtion AVERage")

    def get_average_all(
        self,
    ):
        """CALCulate:AVERage:ALL? を取得する。

        統計機能によって蓄積された全データの要約を問い合わせる。

        Returns:
            AverageStats: 最小、最大、平均、数を格納したオブジェクト

        Raises:
            ValueError: カンマ区切りの応答要素数が4個でなかった場合
        """
        raw = self.query("CALCulate:AVERage:ALL?")
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) != 4:
            raise ValueError(
                "unexpected CALCulate:AVERage:ALL? response: {0}".format(raw)
            )
        return AverageStats(
            minimum=float(parts[0]),
            maximum=float(parts[1]),
            average=float(parts[2]),
            count=int(float(parts[3])),
        )

    def set_rate(
        self,
        speed,
    ):
        """測定速度を設定する。speed は F, M, S のいずれかである。

        Args:
            speed (str): 'F' (Fast), 'M' (Medium), 'S' (Slow / Low speed)
        """
        self.write("RATE {0}".format(speed))

    def get_rate(
        self,
    ):
        """測定速度を取得する。

        Returns:
            str: 現在の測定速度文字 ('F', 'M', または 'S')
        """
        return self.query("RATE?")

    def meas_raw(
        self,
    ):
        """MEAS? の応答を文字列のまま返す。

        Returns:
            str: デバイスから返却されたカンマ区切りの生の測定データ文字列
        """
        return self.query("MEAS?")

    def meas(
        self,
    ):
        """MEAS? の応答を数値化して返す。

        カンマ区切りで戻ってくる主表示および副表示の測定値文字列を分解し、
        要素数に応じて単一の float または 2 要素のタプルとして返却する。

        Returns:
            float or tuple: 1要素の場合は単一の float、2要素の場合は (主表示, 副表示) の float タプル

        Raises:
            ValueError: 要素数が 1 または 2 のいずれでもない予期せぬ応答パターンだった場合
        """
        raw = self.meas_raw()
        values = [float(v.strip()) for v in raw.split(",")]
        if len(values) == 1:
            return values[0]
        if len(values) == 2:
            return values[0], values[1]
        raise ValueError("unexpected MEAS? response: {0}".format(raw))

    def meas_main(
        self,
    ):
        """MEAS1? により主表示の測定値を取得する。

        Returns:
            float: 主画面に表示されている最新の測定数値
        """
        return self.query_float("MEAS1?")

    def meas_sub(
        self,
    ):
        """MEAS2? により副表示の測定値を取得する。

        Returns:
            float: 副画面に表示されている最新の測定数値
        """
        return self.query_float("MEAS2?")


def main(
    config_path="xdm1000_example.yml",
):
    """SCPI クラス単独の動作確認用サンプルである。

    ローカルの設定ファイルを読み込み、インスタンス化を行ってから
    直流電圧 (DCV)・ミディアムレートの設定を行い、10回の主表示測定値を
    連続して取得・出力するスタンドアロンデモ。

    Args:
        config_path (str): 読み込む yaml 設定ファイルのパス。デフォルトは 'xdm1000_example.yml'
    """
    from xdm1000.config import Config

    config = None
    try:
        config = Config(config_path)
    except Exception:
        config = None

    # ポートのオープンと通信条件確立
    # IP 仕様ではなくて port のみ (USBなので)
    dmm = Xdm1000Scpi(
        # port="/dev/cu.usbserial-10",
        # timeout=2.0,
        # baudrate=115200,
        config=config,
    )

    try:
        print("IDN:", dmm.idn())
        dmm.configure_voltage_dc("AUTO")  # オートレンジ直流電圧測定に初期設定
        dmm.set_rate("M")  # 測定速度を Medium に指定
        time.sleep(0.5)  # 装置側の設定安定化待ちスリープ

        # 0.5秒間隔で10回サンプリング
        for _ in range(10):
            print(dmm.meas_main())
            time.sleep(0.5)
    finally:
        # 例外発生時でも確実にポートを閉じるガード構造
        dmm.close()


if __name__ == "__main__":
    main()
