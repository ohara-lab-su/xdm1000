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
* x_logger を優先して logger を作る。
* with 構文の利用は前提にしない。
* Python 3.6 以下互換の文法だけを使う。
"""

import serial

try:
    from x_logger import get_logger
except Exception:
    get_logger = None


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
            logger_name = "xdm1000_scpi"
            if config is not None:
                logger_name = getattr(config, "SERVER_LOGGER_NAME", logger_name)
            try:
                logger = get_logger(logger_name, level=log_level)
            except TypeError:
                logger = get_logger(logger_name)
            except Exception:
                logger = None
        self.logger = logger

        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            write_timeout=timeout,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
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
        if self.logger is not None:
            try:
                self.logger.debug("SCPI WRITE: %s", command.rstrip())
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
        if self.logger is not None:
            try:
                self.logger.debug("SCPI READ : %s", text)
            except Exception:
                pass
        return text

    def query(
        self,
        command,
    ):
        """
        SCPI query を送信し、1 行応答を返す。
        """
        self.ser.reset_input_buffer()
        self.write(command)
        response = self.read_line()
        if response == "":
            raise TimeoutError("no response from XDM1000: {0}".format(command))
        return response

    def query_float(
        self,
        command,
    ):
        """
        SCPI query 応答を float として返す。
        """
        return float(self.query(command))

    def query_int(
        self,
        command,
    ):
        """
        SCPI query 応答を int として返す。
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
        remote mode へ切り替える。
        """
        self.write("SYSTem:REMote")

    def local(
        self,
    ):
        """
        local mode へ戻す。
        """
        self.write("SYSTem:LOCal")

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

    def set_rate(
        self,
        speed,
    ):
        """
        RATE を設定する。
        """
        self.write("RATE {0}".format(speed))

    def get_rate(
        self,
    ):
        """
        RATE? を返す。
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
        MEAS1? を返す。
        """
        return self.query_float("MEAS1?")

    def meas_sub(
        self,
    ):
        """
        MEAS2? を返す。
        """
        return self.query_float("MEAS2?")

    def set_calc_function_average(
        self,
    ):
        """
        CALCulate:FUNCtion AVERage を設定する。
        """
        self.write("CALCulate:FUNCtion AVERage")

    def calc_average_all(
        self,
    ):
        """
        CALCulate:AVERage:ALL? を解釈して返す。
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


def main():
    """
    低レベル SCPI 動作確認用の簡易サンプルである。
    引数は使わず、この関数内の設定だけで動かす。
    """
    try:
        from xdm1000.config import Config
        cfg = Config()
    except Exception:
        cfg = None

    port = "/dev/cu.usbserial-10"
    timeout = 2.0
    baudrate = 115200

    dmm = Xdm1000Scpi(
        port=port,
        timeout=timeout,
        baudrate=baudrate,
        config=cfg,
    )

    try:
        print("IDN:", dmm.idn())
        dmm.configure_voltage_dc("AUTO")
        dmm.set_rate("F")
        print("MEAS1:", dmm.meas_main())
    finally:
        dmm.close()


if __name__ == "__main__":
    main()
