#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OWON XDM1000 / XDM1241 用の低レベル SCPI ラッパである。

この層はシリアルポートと SCPI コマンド送受信だけを担当する。
測定条件のキャッシュ、process 制御、上位 API 状態管理は持たない。

設計方針
--------
* 低レベルの SCPI 送受信だけを行う。
* コンストラクタ引数だけでも動作する。
* config オブジェクトが与えられた場合は config 側を優先する。
* logger の初期化は cobotta_ctrl の流儀に揃える。
* with 構文の利用は前提にしない。
* Python 3.6 以下互換の文法だけを使う。
"""

import logging
import time
import serial


class AverageStats(object):
    """
    CALCulate:AVERage:ALL? の結果を保持する。
    """

    def __init__(
        self,
        minimum,
        maximum,
        average,
        count,
    ):
        self.minimum = minimum
        self.maximum = maximum
        self.average = average
        self.count = count

    def to_dict(
        self,
    ):
        """
        dict へ変換する。
        """
        return {
            "minimum": self.minimum,
            "maximum": self.maximum,
            "average": self.average,
            "count": self.count,
        }


class Xdm1000Scpi(object):
    """
    OWON XDM1000 系に SCPI コマンドを送る低レベル制御クラスである。
    """

    def __init__(
        self,
        port=None,
        timeout=1.0,
        baudrate=115200,
        logger=None,
        log_level=None,
        config=None,
    ):
        """
        USB-Serial ポートを開く。

        引数だけでも設定できる。
        config が与えられた場合は PORT, TIMEOUT, BAUDRATE, LOGGER_LEVEL を
        config 側から優先して読む。
        """
        if logger is None:
            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            logger = logging.getLogger(__name__)

        self._logger = logger
        self._config = config

        if config is not None:
            port = getattr(config, "PORT", port)
            timeout = getattr(config, "TIMEOUT", timeout)
            baudrate = getattr(config, "BAUDRATE", baudrate)

        if port is None:
            raise ValueError("port が必要である。")

        # pyserial.Serial() の型警告を避けるため、
        # 呼び出し直前で引数型を明示しておく。
        self._port = str(port)
        self._timeout = float(timeout)
        self._baudrate = int(baudrate)

        serial_port = self._port
        serial_baudrate = int(self._baudrate)
        serial_bytesize = int(serial.EIGHTBITS)
        serial_parity = str(serial.PARITY_NONE)
        serial_stopbits = int(serial.STOPBITS_ONE)
        serial_timeout = float(self._timeout)
        serial_write_timeout = float(self._timeout)
        serial_xonxoff = False
        serial_rtscts = False
        serial_dsrdtr = False

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

    def close(
        self,
    ):
        """
        シリアルポートを閉じる。
        """
        if self.ser is not None and self.ser.is_open:
            self.ser.close()

    def disconnect(
        self,
    ):
        """
        close の別名である。
        """
        self.close()

    def __del__(
        self,
    ):
        """
        破棄時に local へ戻して閉じる。
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

    def read_line(
        self,
    ):
        """
        1 行応答を返す。
        """
        raw = self.ser.readline()
        if not raw:
            raise TimeoutError("SCPI 応答 timeout")
        text = raw.decode("ascii", errors="replace").strip()
        try:
            self._logger.debug("SCPI READ : %s", text)
        except Exception:
            pass
        return text

    def query(
        self,
        command,
    ):
        """
        query を 1 回実行する。
        """
        self.write(command)
        return self.read_line()

    def query_float(
        self,
        command,
    ):
        """
        浮動小数応答を返す。
        """
        return float(self.query(command))

    def query_int(
        self,
        command,
    ):
        """
        整数応答を返す。
        """
        return int(float(self.query(command)))

    def idn(
        self,
    ):
        """
        *IDN? を返す。
        """
        return self.query("*IDN?")

    def reset(
        self,
    ):
        """
        *RST を送る。
        """
        self.write("*RST")

    def remote(
        self,
    ):
        """
        remote へ切り替える。
        """
        self.write("SYSTem:REMote")

    def local(
        self,
    ):
        """
        local へ戻す。
        """
        self.write("SYSTem:LOCal")

    def set_beeper(
        self,
        enabled,
    ):
        """
        ブザーの ON/OFF を設定する。
        """
        if enabled:
            self.write("SYSTem:BEEPer:STATe ON")
        else:
            self.write("SYSTem:BEEPer:STATe OFF")

    def get_beeper(
        self,
    ):
        """
        ブザー状態を取得する。
        """
        return self.query_int("SYSTem:BEEPer:STATe?") != 0

    def configure_voltage_dc(
        self,
        range_value="AUTO",
    ):
        self.write("CONFigure:VOLTage:DC {0}".format(range_value))

    def configure_voltage_ac(
        self,
        range_value="AUTO",
    ):
        self.write("CONFigure:VOLTage:AC {0}".format(range_value))

    def configure_current_dc(
        self,
        range_value="AUTO",
    ):
        self.write("CONFigure:CURRent:DC {0}".format(range_value))

    def configure_current_ac(
        self,
        range_value="AUTO",
    ):
        self.write("CONFigure:CURRent:AC {0}".format(range_value))

    def configure_resistance(
        self,
        range_value="AUTO",
    ):
        self.write("CONFigure:RESistance {0}".format(range_value))

    def configure_fresistance(
        self,
        range_value="AUTO",
    ):
        self.write("CONFigure:FRESistance {0}".format(range_value))

    def configure_frequency(
        self,
    ):
        self.write("CONFigure:FREQuency")

    def configure_period(
        self,
    ):
        self.write("CONFigure:PERiod")

    def configure_capacitance(
        self,
        range_value="AUTO",
    ):
        self.write("CONFigure:CAPacitance {0}".format(range_value))

    def configure_temperature_rtd(
        self,
    ):
        self.write("CONFigure:TEMPerature:RTD")

    def configure_diode(
        self,
    ):
        self.write("CONFigure:DIODe")

    def configure_continuity(
        self,
    ):
        self.write("CONFigure:CONTinuity")

    def set_calc_function_average(
        self,
    ):
        self.write("CALCulate:FUNCtion AVERage")

    def get_average_all(
        self,
    ):
        """
        CALCulate:AVERage:ALL? を取得する。
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
        """
        測定速度を設定する。
        """
        self.write("RATE {0}".format(speed))

    def get_rate(
        self,
    ):
        """
        測定速度を取得する。
        """
        return self.query("RATE?")

    def meas_raw(
        self,
    ):
        """
        MEAS? の生応答を返す。
        """
        return self.query("MEAS?")

    def meas(
        self,
    ):
        """
        MEAS? を解釈して返す。
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
        """
        MEAS1? により主表示の測定値を取得する。
        """
        return self.query_float("MEAS1?")

    def meas_sub(
        self,
    ):
        """
        MEAS2? により副表示の測定値を取得する。
        """
        return self.query_float("MEAS2?")


def main(
    config_path="xdm1000_example.yml",
):
    """
    SCPI 単独動作確認用サンプルである。
    """
    from xdm1000.config import Config

    config = None
    try:
        config = Config(config_path)
    except Exception:
        config = None

    dmm = Xdm1000Scpi(
        port="/dev/cu.usbserial-10",
        timeout=2.0,
        baudrate=115200,
        config=config,
    )

    try:
        print("IDN:", dmm.idn())
        dmm.configure_voltage_dc("AUTO")
        dmm.set_rate("F")
        time.sleep(0.2)

        for _ in range(10):
            print(dmm.meas_main())
            time.sleep(0.2)
    finally:
        dmm.close()


if __name__ == "__main__":
    main()
