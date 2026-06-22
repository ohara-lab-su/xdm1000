#!/usr/bin/env python
# coding:utf-8
"""
OWON XDM1241 / XDM1000 系デジタルマルチメータ用 SCPI ラッパである。
XDM1000 系共通

このファイルは pyserial 経由で USB-Serial 接続された XDM1241 に SCPI を送る。
XDM1041/XDM2041 用として公開されている XDM1000 Series Programming Manual に
記載された SCPI コマンドを一通り薄く包む。
"""

import time
import serial


class AverageStats(object):
    """
    CALCulate:AVERage:ALL? の結果を保持するクラスである。
    """

    def __init__(self, minimum, maximum, average, count):
        """インスタンスを初期化する。"""
        self.minimum = minimum
        self.maximum = maximum
        self.average = average
        self.count = count


class Xdm1000Scpi(object):
    """
    OWON XDM1000 系に SCPI コマンドを送る低レベル制御クラスである。
    """

    def __init__(
        self,
        port,
        timeout=1.0,
        baudrate=115200,
        logger=None,
        log_level=None,
        config=None,
    ):
        """
        USB-Serial ポートを開く。

        コンストラクタ引数だけでも設定できる。
        config が与えられた場合は config 側を優先する。
        """
        if logger is None:
            import logging

            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            logger = logging.getLogger(__name__)

        self._logger = logger
        self._config = config

        if config is not None:
            port = getattr(config, "PORT", port)
            timeout = getattr(config, "TIMEOUT", timeout)
            baudrate = getattr(config, "BAUDRATE", baudrate)

        self._port = str(port)
        self._timeout = float(timeout)
        self._baudrate = int(baudrate)

        serial_port = self._port
        serial_baudrate = self._baudrate
        serial_bytesize = int(serial.EIGHTBITS)
        serial_parity = str(serial.PARITY_NONE)
        serial_stopbits = int(serial.STOPBITS_ONE)
        serial_timeout = self._timeout
        serial_write_timeout = self._timeout
        serial_xonxoff = bool(False)
        serial_rtscts = bool(False)
        serial_dsrdtr = bool(False)

        self.ser = serial.Serial(
            port=serial_port,
            baudrate=serial_baudrate,
            bytesize=serial_bytesize,
            parity=serial_parity,
            stopbits=serial_stopbits,
            timeout=serial_timeout,
            write_timeout=serial_write_timeout,
            xonxoff=serial_xonxoff,
            rtscts=serial_rtscts,
            dsrdtr=serial_dsrdtr,
        )

    def close(self):
        """
        シリアルポートを閉じる。
        """
        if self.ser is not None and self.ser.is_open:
            self.ser.close()

    def disconnect(self):
        """
        サーバー停止時に呼ばれる解放用エイリアスである。
        """
        self.close()

    def __del__(self):
        """
        オブジェクト破棄時に local mode へ戻して解放する。
        """
        try:
            self.local()
        except Exception:
            pass

        try:
            self.close()
        except Exception:
            pass

    def write(self, command):
        """
        SCPI コマンドを送信する。
        """
        if not command.endswith("\n"):
            command += "\n"
        try:
            self._logger.debug("SCPI WRITE: %s", command.rstrip())
        except Exception:
            pass
        self.ser.write(command.encode("ascii"))
        self.ser.flush()

    def query(self, command):
        """
        SCPI クエリを送信し、1 行の応答文字列を返す。
        """
        self.ser.reset_input_buffer()
        self.write(command)

        response = self.ser.readline().decode("ascii", errors="replace").strip()
        if response == "":
            raise TimeoutError("no response from XDM1241: {0}".format(command))

        try:
            self._logger.debug("SCPI READ : %s", response)
        except Exception:
            pass
        return response

    def query_float(self, command):
        """
        SCPI クエリ応答を float として返す。
        """
        return float(self.query(command))

    def query_int(self, command):
        """
        SCPI クエリ応答を int として返す。
        """
        return int(float(self.query(command)))

    def idn(self):
        """
        *IDN? により機器識別文字列を取得する。
        """
        return self.query("*IDN?")

    def reset(self):
        """
        *RST により機器設定をデフォルトに戻す。
        """
        self.write("*RST")

    def remote(self):
        """
        SYSTem:REMote により SCPI remote mode に入る。
        """
        self.write("SYSTem:REMote")

    def local(self):
        """
        SYSTem:LOCal により SCPI mode を終了し、ローカル操作へ戻す。
        """
        self.write("SYSTem:LOCal")

    def set_beeper(self, enabled):
        """
        ブザーの ON/OFF を設定する。
        """
        if enabled:
            self.write("SYSTem:BEEPer:STATe ON")
        else:
            self.write("SYSTem:BEEPer:STATe OFF")

    def get_beeper(self):
        """
        ブザー状態を取得する。True が ON、False が OFF である。
        """
        return self.query_int("SYSTem:BEEPer:STATe?") != 0

    def configure_voltage_dc(self, range_value="AUTO"):
        """configure_voltage_dc を実行する。"""
        self.write("CONFigure:VOLTage:DC {0}".format(range_value))

    def configure_voltage_ac(self, range_value="AUTO"):
        """configure_voltage_ac を実行する。"""
        self.write("CONFigure:VOLTage:AC {0}".format(range_value))

    def configure_current_dc(self, range_value="AUTO"):
        """configure_current_dc を実行する。"""
        self.write("CONFigure:CURRent:DC {0}".format(range_value))

    def configure_current_ac(self, range_value="AUTO"):
        """configure_current_ac を実行する。"""
        self.write("CONFigure:CURRent:AC {0}".format(range_value))

    def configure_resistance(self, range_value="AUTO"):
        """configure_resistance を実行する。"""
        self.write("CONFigure:RESistance {0}".format(range_value))

    def configure_fresistance(self, range_value="AUTO"):
        """configure_fresistance を実行する。"""
        self.write("CONFigure:FRESistance {0}".format(range_value))

    def configure_frequency(self):
        """configure_frequency を実行する。"""
        self.write("CONFigure:FREQuency")

    def configure_period(self):
        """configure_period を実行する。"""
        self.write("CONFigure:PERiod")

    def configure_capacitance(self, range_value="AUTO"):
        """configure_capacitance を実行する。"""
        self.write("CONFigure:CAPacitance {0}".format(range_value))

    def configure_temperature_rtd(self):
        """configure_temperature_rtd を実行する。"""
        self.write("CONFigure:TEMPerature:RTD")

    def configure_diode(self):
        """configure_diode を実行する。"""
        self.write("CONFigure:DIODe")

    def configure_continuity(self):
        """configure_continuity を実行する。"""
        self.write("CONFigure:CONTinuity")

    def set_calc_function_average(self):
        """set_calc_function_average を実行する。"""
        self.write("CALCulate:FUNCtion AVERage")

    def get_average_all(self):
        """
        CALCulate:AVERage:ALL? を取得する。
        """
        raw = self.query("CALCulate:AVERage:ALL?")
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) != 4:
            raise ValueError("unexpected CALCulate:AVERage:ALL? response: {0}".format(raw))
        return AverageStats(
            minimum=float(parts[0]),
            maximum=float(parts[1]),
            average=float(parts[2]),
            count=int(float(parts[3])),
        )

    def set_rate(self, speed):
        """
        測定速度を設定する。speed は F, M, L のいずれかである。
        """
        self.write("RATE {0}".format(speed))

    def get_rate(self):
        """
        測定速度を取得する。F が高速、M が中速、L が低速である。
        """
        return self.query("RATE?")

    def meas_raw(self):
        """
        MEAS? の応答を文字列のまま返す。
        """
        return self.query("MEAS?")

    def meas(self):
        """
        MEAS? の応答を数値化して返す。
        """
        raw = self.meas_raw()
        values = [float(v.strip()) for v in raw.split(",")]
        if len(values) == 1:
            return values[0]
        if len(values) == 2:
            return values[0], values[1]
        raise ValueError("unexpected MEAS? response: {0}".format(raw))

    def meas_main(self):
        """
        MEAS1? により主表示の測定値を取得する。
        """
        return self.query_float("MEAS1?")

    def meas_sub(self):
        """
        MEAS2? により副表示の測定値を取得する。
        """
        return self.query_float("MEAS2?")


def main():
    """
    DC 電圧を 10 回読む最小サンプルである。
    """
    # port = "/dev/cu.usbserial-140"
    port = "/dev/cu.usbserial-10"

    dmm = Xdm1000Scpi(port)

    try:
        print("IDN:", dmm.idn())
        dmm.configure_voltage_dc("AUTO")
        dmm.set_rate("M")
        time.sleep(0.5)

        for _ in range(10):
            print(dmm.meas_main())
            time.sleep(0.5)
    finally:
        dmm.close()


if __name__ == "__main__":
    main()
