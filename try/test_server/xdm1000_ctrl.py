# 保存先: xdm1241_scpi.py
#!/usr/bin/env python3
"""
OWON XDM1000 / XDM1000 系デジタルマルチメータ用 SCPI ラッパである。

このファイルは pyserial 経由で USB-Serial 接続された XDM1000 に SCPI を送る。
XDM1041/XDM2041 用として公開されている XDM1000 Series Programming Manual に
記載された SCPI コマンドを一通り薄く包む。

必要:
    pip install pyserial

使用例:
    python xdm1241_scpi.py /dev/ttyUSB0
    python xdm1241_scpi.py /dev/tty.usbserial-XXXX
    python xdm1241_scpi.py COM3
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union
import sys
import time

import serial

ScpiValue = Union[str, int, float]


@dataclass(frozen=True)
class AverageStats:
    """CALCulate:AVERage:ALL? の結果を保持するデータクラスである。"""

    minimum: float
    maximum: float
    average: float
    count: int


class XDM1241:
    """OWON XDM1000 に SCPI コマンドを送る低レベル制御クラスである。"""

    def __init__(
        self,
        port: str,
        timeout: float = 1.0,
        baudrate: int = 115200,
    ) -> None:
        """USB-Serial ポートを開く。"""
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

    def close(self) -> None:
        """シリアルポートを閉じる。"""
        self.ser.close()

    def __enter__(self) -> "XDM1000":
        """with 文用のエントリである。"""
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """with 文終了時にシリアルポートを閉じる。"""
        self.close()

    def write(self, command: str) -> None:
        """SCPI コマンドを送信する。"""
        if not command.endswith("\n"):
            command += "\n"
        self.ser.write(command.encode("ascii"))
        self.ser.flush()

    def query(self, command: str) -> str:
        """SCPI クエリを送信し、1 行の応答文字列を返す。"""
        self.ser.reset_input_buffer()
        self.write(command)
        response = self.ser.readline().decode("ascii", errors="replace").strip()
        if response == "":
            raise TimeoutError(f"no response from XDM1000: {command}")
        return response

    def query_float(self, command: str) -> float:
        """SCPI クエリ応答を float として返す。"""
        return float(self.query(command))

    def query_int(self, command: str) -> int:
        """SCPI クエリ応答を int として返す。"""
        return int(float(self.query(command)))

    # IEEE488.2 common commands

    def idn(self) -> str:
        """*IDN? により機器識別文字列を取得する。"""
        return self.query("*IDN?")

    def reset(self) -> None:
        """*RST により機器設定をデフォルトに戻す。"""
        self.write("*RST")

    # SYSTem subsystem

    def remote(self) -> None:
        """SYSTem:REMote により SCPI remote mode に入る。"""
        self.write("SYSTem:REMote")

    def local(self) -> None:
        """SYSTem:LOCal により SCPI mode を終了し、ローカル操作へ戻す。"""
        self.write("SYSTem:LOCal")

    def set_beeper(self, enabled: bool) -> None:
        """ブザーの ON/OFF を設定する。"""
        self.write(f"SYSTem:BEEPer:STATe {'ON' if enabled else 'OFF'}")

    def get_beeper(self) -> bool:
        """ブザー状態を取得する。True が ON、False が OFF である。"""
        return self.query_int("SYSTem:BEEPer:STATe?") != 0

    # SENSe subsystem

    def set_function(self, function: str, display: int = 1) -> None:
        """測定ファンクションを設定する。display は 1 が主表示、2 が副表示である。"""
        self.write(f'SENSe:FUNCtion{display} "{function}"')

    def get_function(self, display: int = 1) -> str:
        """測定ファンクションを取得する。"""
        return self.query(f"SENSe:FUNCtion{display}?").strip('"')

    def set_temperature_rtd_type(self, rtd_type: str) -> None:
        """RTD 種別を設定する。例: KITS90, PT100。"""
        self.write(f"SENSe:TEMPerature:RTD:TYPe {rtd_type}")

    def get_temperature_rtd_type(self) -> str:
        """RTD 種別を取得する。"""
        return self.query("SENSe:TEMPerature:RTD:TYPe?")

    def set_temperature_unit(self, unit: str) -> None:
        """温度単位を設定する。unit は C, F, K のいずれかである。"""
        self.write(f"SENSe:TEMPerature:RTD:UNIT {unit}")

    def get_temperature_unit(self) -> str:
        """温度単位を取得する。"""
        return self.query("SENSe:TEMPerature:RTD:UNIT?")

    def set_temperature_show(self, mode: str) -> None:
        """温度表示モードを設定する。mode は TEMP, MEAS, ALL のいずれかである。"""
        self.write(f"SENSe:TEMPerature:RTD:SHOW {mode}")

    def get_temperature_show(self) -> str:
        """温度表示モードを取得する。"""
        return self.query("SENSe:TEMPerature:RTD:SHOW?")

    def set_continuity_threshold(self, value: ScpiValue) -> None:
        """導通判定しきい値を設定する。"""
        self.write(f"SENSe:CONTinuity:THREshold {value}")

    # CONFigure subsystem

    def configure_voltage_dc(self, range_value: ScpiValue = "AUTO") -> None:
        """DC 電圧測定に切り替え、レンジを設定する。"""
        self.write(f"CONFigure:VOLTage:DC {range_value}")

    def configure_voltage_ac(self, range_value: ScpiValue = "AUTO") -> None:
        """AC 電圧測定に切り替え、レンジを設定する。"""
        self.write(f"CONFigure:VOLTage:AC {range_value}")

    def configure_current_dc(self, range_value: ScpiValue = "AUTO") -> None:
        """DC 電流測定に切り替え、レンジを設定する。"""
        self.write(f"CONFigure:CURRent:DC {range_value}")

    def configure_current_ac(self, range_value: ScpiValue = "AUTO") -> None:
        """AC 電流測定に切り替え、レンジを設定する。"""
        self.write(f"CONFigure:CURRent:AC {range_value}")

    def configure_resistance(self, range_value: ScpiValue = "AUTO") -> None:
        """2 線式抵抗測定に切り替え、レンジを設定する。"""
        self.write(f"CONFigure:RESistance {range_value}")

    def configure_fresistance(self, range_value: ScpiValue = "AUTO") -> None:
        """4 線式抵抗測定に切り替え、レンジを設定する。"""
        self.write(f"CONFigure:FRESistance {range_value}")

    def configure_frequency(self) -> None:
        """周波数測定に切り替える。"""
        self.write("CONFigure:FREQuency")

    def configure_period(self) -> None:
        """周期測定に切り替える。"""
        self.write("CONFigure:PERiod")

    def configure_capacitance(self, range_value: ScpiValue = "AUTO") -> None:
        """静電容量測定に切り替え、レンジを設定する。"""
        self.write(f"CONFigure:CAPacitance {range_value}")

    def configure_temperature_rtd(self, rtd_type: Optional[str] = None) -> None:
        """RTD 温度測定に切り替える。rtd_type を指定した場合は種別も設定する。"""
        if rtd_type is None:
            self.write("CONFigure:TEMPerature:RTD")
        else:
            self.write(f"CONFigure:TEMPerature:RTD {rtd_type}")

    def configure_diode(self) -> None:
        """ダイオード測定に切り替える。"""
        self.write("CONFigure:DIODe")

    def configure_continuity(self) -> None:
        """導通テストに切り替える。"""
        self.write("CONFigure:CONTinuity")

    # CALCulate subsystem

    def get_average_all(self) -> AverageStats:
        """統計値の minimum, maximum, average, count を取得する。"""
        raw = self.query("CALCulate:AVERage:ALL?")
        values = [v.strip() for v in raw.split(",")]
        if len(values) != 4:
            raise ValueError(f"unexpected CALCulate:AVERage:ALL? response: {raw}")
        return AverageStats(
            minimum=float(values[0]),
            maximum=float(values[1]),
            average=float(values[2]),
            count=int(float(values[3])),
        )

    def get_average(self) -> float:
        """統計平均値を取得する。"""
        return self.query_float("CALCulate:AVERage:AVERage?")

    def get_average_maximum(self) -> float:
        """統計最大値を取得する。"""
        return self.query_float("CALCulate:AVERage:MAXimum?")

    def get_average_minimum(self) -> float:
        """統計最小値を取得する。"""
        return self.query_float("CALCulate:AVERage:MINimum?")

    def set_db_reference(self, resistance_ohm: ScpiValue) -> None:
        """dB 計算用の基準抵抗を設定する。"""
        self.write(f"CALCulate:DB:REFerence {resistance_ohm}")

    def get_db_reference(self) -> float:
        """dB 計算用の基準抵抗を取得する。"""
        return self.query_float("CALCulate:DB:REFerence?")

    def set_dbm_reference(self, resistance_ohm: ScpiValue) -> None:
        """dBm 計算用の基準抵抗を設定する。"""
        self.write(f"CALCulate:DBM:REFerence {resistance_ohm}")

    def get_dbm_reference(self) -> float:
        """dBm 計算用の基準抵抗を取得する。"""
        return self.query_float("CALCulate:DBM:REFerence?")

    def set_calc_function(self, function: str) -> None:
        """数学機能を設定する。function は NULL, DB, DBM, AVERage のいずれかである。"""
        self.write(f"CALCulate:FUNCtion {function}")

    def get_calc_function(self) -> str:
        """現在の数学機能を取得する。"""
        return self.query("CALCulate:FUNCtion?")

    def set_null_offset(self, value: ScpiValue) -> None:
        """NULL 機能の相対値を設定する。"""
        self.write(f"CALCulate:NULL:OFFSet {value}")

    def get_null_offset(self, selector: Optional[str] = None) -> float:
        """NULL 機能の相対値を取得する。selector は MINimum または MAXimum を指定できる。"""
        if selector is None:
            return self.query_float("CALCulate:NULL:OFFSet?")
        return self.query_float(f"CALCulate:NULL:OFFSet? {selector}")

    def calc_off(self) -> None:
        """数学機能を OFF にする。"""
        self.write("CALCulate:STATe OFF")

    # Other commands

    def auto(self) -> None:
        """AUTO により autoscale を有効にする。"""
        self.write("AUTO")

    def get_auto(self) -> bool:
        """autoscale 状態を取得する。True が auto、False が manual である。"""
        return self.query_int("AUTO?") != 0

    def set_range(self, range_index: Union[int, str]) -> None:
        """現在の測定機能に対してレンジ番号または DEF を設定する。"""
        self.write(f"RANGE {range_index}")

    def set_rate(self, speed: str) -> None:
        """測定速度を設定する。speed は F, M, L のいずれかである。"""
        self.write(f"RATE {speed}")

    def get_rate(self) -> str:
        """測定速度を取得する。F が高速、M が中速、L が低速である。"""
        return self.query("RATE?")

    def meas_raw(self) -> str:
        """MEAS? の応答を文字列のまま返す。副表示ありの場合はカンマ区切りで返る。"""
        return self.query("MEAS?")

    def meas(self) -> Union[float, tuple[float, float]]:
        """MEAS? の応答を数値化して返す。副表示ありの場合は 2 要素 tuple を返す。"""
        raw = self.meas_raw()
        values = [float(v.strip()) for v in raw.split(",")]
        if len(values) == 1:
            return values[0]
        if len(values) == 2:
            return values[0], values[1]
        raise ValueError(f"unexpected MEAS? response: {raw}")

    def meas_main(self) -> float:
        """MEAS1? により主表示の測定値を取得する。"""
        return self.query_float("MEAS1?")

    def meas_sub(self) -> float:
        """MEAS2? により副表示の測定値を取得する。"""
        return self.query_float("MEAS2?")


def main() -> None:
    """DC 電圧を 10 回読む最小サンプルである。"""
    # port = "/dev/ttyUSB0"
    # port = "/dev/cu.usbserial-140"
    port = "/dev/cu.usbserial-10"

    with XDM1241(port) as dmm:

        dmm.remote()

        try:
            print("IDN:", dmm.idn())
            dmm.configure_voltage_dc("AUTO")
            dmm.set_rate("M")
            time.sleep(0.5)

            for _ in range(10):
                print(dmm.meas_main())
                time.sleep(0.5)

        finally:
            dmm.local()

    with XDM1241(port) as dmm:
        dmm.remote()
        try:
            print("IDN:", dmm.idn())

            dmm.configure_voltage_dc("AUTO")
            dmm.set_rate("M")
            time.sleep(0.5)

            for _ in range(10):
                print(dmm.meas_main())
                time.sleep(0.5)

        finally:
            dmm.local()


if __name__ == "__main__":
    main()
