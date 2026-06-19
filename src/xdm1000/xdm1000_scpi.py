#!/usr/bin/env python3
"""OWON XDM1000 / XDM1241 系デジタルマルチメータ用 SCPI ドライバである。

この層は上位の測定制御 API ではなく、SCPI コマンドを Python メソッドへ薄く
写像する低レベルドライバである。測定器としての使いやすい API は
xdm1000_ctrl.py 側で提供する。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union
import time

import serial

ScpiValue = Union[str, int, float]
MeasureValue = Union[float, tuple[float, float]]


@dataclass(frozen=True)
class AverageStats:
    """CALCulate:AVERage:ALL? の結果である。"""

    minimum: float
    maximum: float
    average: float
    count: int


class XDM1000SCPI:
    """OWON XDM1000 / XDM1241 へ SCPI を送る低レベルドライバである。"""

    def __init__(
        self,
        port: str,
        timeout: float = 1.0,
        baudrate: int = 115200,
        logger=None,
    ) -> None:
        """USB-Serial ポートを開く。"""
        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate
        self._logger = logger
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

    # ------------------------------------------------------------------
    # lifetime / primitive I/O
    # ------------------------------------------------------------------

    def close(self) -> None:
        """シリアルポートを閉じる。"""
        if self.ser.is_open:
            self.ser.close()

    def disconnect(self) -> None:
        """サーバー停止時に呼ばれる解放用エイリアスである。"""
        self.close()

    def __enter__(self) -> "XDM1000SCPI":
        """with 文用のエントリである。"""
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """with 文終了時にシリアルポートを閉じる。"""
        self.close()

    def write(self, command: str) -> None:
        """SCPI コマンドを送信する。"""
        if not command.endswith("\n"):
            command += "\n"
        if self._logger is not None:
            self._logger.debug("SCPI write: %s", command.rstrip())
        self.ser.write(command.encode("ascii"))
        self.ser.flush()

    def query(self, command: str) -> str:
        """SCPI クエリを送信し、1 行の応答文字列を返す。"""
        self.ser.reset_input_buffer()
        self.write(command)
        response = self.ser.readline().decode("ascii", errors="replace").strip()
        if self._logger is not None:
            self._logger.debug("SCPI response: %s", response)
        if response == "":
            raise TimeoutError(f"no response from XDM1000: {command}")
        return response

    def query_float(self, command: str) -> float:
        """SCPI クエリ応答を float として返す。"""
        return float(self.query(command))

    def query_int(self, command: str) -> int:
        """SCPI クエリ応答を int として返す。"""
        return int(float(self.query(command)))

    def query_bool(self, command: str) -> bool:
        """SCPI クエリ応答を bool として返す。"""
        return self.query_int(command) != 0

    # ------------------------------------------------------------------
    # IEEE488.2 common commands
    # ------------------------------------------------------------------

    def idn(self) -> str:
        """*IDN? により機器識別文字列を取得する。"""
        return self.query("*IDN?")

    def reset(self) -> None:
        """*RST により機器設定をデフォルトに戻す。"""
        self.write("*RST")

    # ------------------------------------------------------------------
    # SYSTem subsystem
    # ------------------------------------------------------------------

    def remote(self) -> None:
        """SYSTem:REMote により SCPI remote mode に入る。"""
        self.write("SYSTem:REMote")

    def local(self) -> None:
        """SYSTem:LOCal により SCPI mode を終了し、ローカル操作へ戻す。"""
        self.write("SYSTem:LOCal")

    def set_beeper(self, enabled: bool) -> None:
        """SYSTem:BEEPer:STATe でブザーの ON/OFF を設定する。"""
        self.write(f"SYSTem:BEEPer:STATe {'ON' if enabled else 'OFF'}")

    def get_beeper(self) -> bool:
        """SYSTem:BEEPer:STATe? でブザー状態を取得する。"""
        return self.query_bool("SYSTem:BEEPer:STATe?")

    # ------------------------------------------------------------------
    # SENSe subsystem
    # ------------------------------------------------------------------

    def set_function(self, function: str, display: int = 1) -> None:
        """[SENSe:]FUNCtion[1|2] で測定ファンクションを設定する。"""
        self.write(f'SENSe:FUNCtion{display} "{function}"')

    def get_function(self, display: int = 1) -> str:
        """[SENSe:]FUNCtion[1|2]? で測定ファンクションを取得する。"""
        return self.query(f"SENSe:FUNCtion{display}?").strip('"')

    def set_main_function(self, function: str) -> None:
        """主表示の測定ファンクションを設定する。"""
        self.set_function(function=function, display=1)

    def get_main_function(self) -> str:
        """主表示の測定ファンクションを取得する。"""
        return self.get_function(display=1)

    def set_sub_function(self, function: str) -> None:
        """副表示の測定ファンクションを設定する。NONe で副表示を閉じる。"""
        self.set_function(function=function, display=2)

    def get_sub_function(self) -> str:
        """副表示の測定ファンクションを取得する。"""
        return self.get_function(display=2)

    def set_temperature_rtd_type(self, rtd_type: str) -> None:
        """[SENSe:]TEMPerature:RTD:TYPe で RTD 種別を設定する。"""
        self.write(f"SENSe:TEMPerature:RTD:TYPe {rtd_type}")

    def get_temperature_rtd_type(self) -> str:
        """[SENSe:]TEMPerature:RTD:TYPe? で RTD 種別を取得する。"""
        return self.query("SENSe:TEMPerature:RTD:TYPe?")

    def set_temperature_unit(self, unit: str) -> None:
        """[SENSe:]TEMPerature:RTD:UNIT で温度単位を設定する。"""
        self.write(f"SENSe:TEMPerature:RTD:UNIT {unit}")

    def get_temperature_unit(self) -> str:
        """[SENSe:]TEMPerature:RTD:UNIT? で温度単位を取得する。"""
        return self.query("SENSe:TEMPerature:RTD:UNIT?")

    def set_temperature_show(self, mode: str) -> None:
        """[SENSe:]TEMPerature:RTD:SHOW で温度表示モードを設定する。"""
        self.write(f"SENSe:TEMPerature:RTD:SHOW {mode}")

    def get_temperature_show(self) -> str:
        """[SENSe:]TEMPerature:RTD:SHOW? で温度表示モードを取得する。"""
        return self.query("SENSe:TEMPerature:RTD:SHOW?")

    def set_continuity_threshold(self, value: ScpiValue) -> None:
        """[SENSe:]CONTinuity:THREshold で導通判定しきい値を設定する。"""
        self.write(f"SENSe:CONTinuity:THREshold {value}")

    def get_continuity_threshold(self) -> float:
        """[SENSe:]CONTinuity:THREshold? で導通判定しきい値を取得する。

        マニュアル本文では set の構文だけが明示されているが、SCPI 系として query を
        持つ個体があるためドライバ層では escape hatch として実装しておく。
        未対応ファームでは TimeoutError になる。
        """
        return self.query_float("SENSe:CONTinuity:THREshold?")

    # ------------------------------------------------------------------
    # CONFigure subsystem
    # ------------------------------------------------------------------

    def configure_voltage_dc(self, range_value: Optional[ScpiValue] = "AUTO") -> None:
        """CONFigure[:SCALar][:VOLTage]:DC で DC 電圧測定へ切り替える。"""
        self._configure_with_optional_range("CONFigure:VOLTage:DC", range_value)

    def configure_voltage_ac(self, range_value: Optional[ScpiValue] = "AUTO") -> None:
        """CONFigure[:SCALar][:VOLTage]:AC で AC 電圧測定へ切り替える。"""
        self._configure_with_optional_range("CONFigure:VOLTage:AC", range_value)

    def configure_current_dc(self, range_value: Optional[ScpiValue] = "AUTO") -> None:
        """CONFigure[:SCALar]:CURRent:DC で DC 電流測定へ切り替える。"""
        self._configure_with_optional_range("CONFigure:CURRent:DC", range_value)

    def configure_current_ac(self, range_value: Optional[ScpiValue] = "AUTO") -> None:
        """CONFigure[:SCALar]:CURRent:AC で AC 電流測定へ切り替える。"""
        self._configure_with_optional_range("CONFigure:CURRent:AC", range_value)

    def configure_resistance(self, range_value: Optional[ScpiValue] = "AUTO") -> None:
        """CONFigure[:SCALar]:RESistance で 2 線式抵抗測定へ切り替える。"""
        self._configure_with_optional_range("CONFigure:RESistance", range_value)

    def configure_fresistance(self, range_value: Optional[ScpiValue] = "AUTO") -> None:
        """CONFigure[:SCALar]:FRESistance で 4 線式抵抗測定へ切り替える。"""
        self._configure_with_optional_range("CONFigure:FRESistance", range_value)

    def configure_frequency(self) -> None:
        """CONFigure[:SCALar]:FREQuency で周波数測定へ切り替える。"""
        self.write("CONFigure:FREQuency")

    def configure_period(self) -> None:
        """CONFigure[:SCALar]:PERiod で周期測定へ切り替える。"""
        self.write("CONFigure:PERiod")

    def configure_capacitance(self, range_value: Optional[ScpiValue] = "AUTO") -> None:
        """CONFigure[:SCALar]:CAPacitance で静電容量測定へ切り替える。"""
        self._configure_with_optional_range("CONFigure:CAPacitance", range_value)

    def configure_temperature_rtd(self, rtd_type: Optional[str] = None) -> None:
        """CONFigure[:SCALar]:TEMPerature:RTD で RTD 温度測定へ切り替える。"""
        if rtd_type is None:
            self.write("CONFigure:TEMPerature:RTD")
        else:
            self.write(f"CONFigure:TEMPerature:RTD {rtd_type}")

    def configure_diode(self) -> None:
        """CONFigure[:SCALar]:DIODe でダイオード測定へ切り替える。"""
        self.write("CONFigure:DIODe")

    def configure_continuity(self) -> None:
        """CONFigure[:SCALar]:CONTinuity で導通テストへ切り替える。"""
        self.write("CONFigure:CONTinuity")

    def _configure_with_optional_range(self, command: str, range_value: Optional[ScpiValue]) -> None:
        """range 省略可能な CONFigure コマンドを送る。"""
        if range_value is None:
            self.write(command)
        else:
            self.write(f"{command} {range_value}")

    # ------------------------------------------------------------------
    # CALCulate subsystem
    # ------------------------------------------------------------------

    def get_average_all(self) -> AverageStats:
        """CALCulate:AVERage:ALL? で minimum, maximum, average, count を取得する。"""
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
        """CALCulate:AVERage:AVERage? で統計平均値を取得する。"""
        return self.query_float("CALCulate:AVERage:AVERage?")

    def get_average_maximum(self) -> float:
        """CALCulate:AVERage:MAXimum? で統計最大値を取得する。"""
        return self.query_float("CALCulate:AVERage:MAXimum?")

    def get_average_minimum(self) -> float:
        """CALCulate:AVERage:MINimum? で統計最小値を取得する。"""
        return self.query_float("CALCulate:AVERage:MINimum?")

    def set_db_reference(self, resistance_ohm: ScpiValue) -> None:
        """CALCulate:DB:REFerence で dB 計算用の基準抵抗を設定する。"""
        self.write(f"CALCulate:DB:REFerence {resistance_ohm}")

    def get_db_reference(self) -> float:
        """CALCulate:DB:REFerence? で dB 計算用の基準抵抗を取得する。"""
        return self.query_float("CALCulate:DB:REFerence?")

    def set_dbm_reference(self, resistance_ohm: ScpiValue) -> None:
        """CALCulate:DBM:REFerence で dBm 計算用の基準抵抗を設定する。"""
        self.write(f"CALCulate:DBM:REFerence {resistance_ohm}")

    def get_dbm_reference(self) -> float:
        """CALCulate:DBM:REFerence? で dBm 計算用の基準抵抗を取得する。"""
        return self.query_float("CALCulate:DBM:REFerence?")

    def set_calc_function(self, function: str) -> None:
        """CALCulate:FUNCtion で数学機能を設定する。"""
        self.write(f"CALCulate:FUNCtion {function}")

    def get_calc_function(self) -> str:
        """CALCulate:FUNCtion? で現在の数学機能を取得する。"""
        return self.query("CALCulate:FUNCtion?")

    def set_null_offset(self, value: ScpiValue) -> None:
        """CALCulate:NULL:OFFSet で NULL 機能の相対値を設定する。"""
        self.write(f"CALCulate:NULL:OFFSet {value}")

    def get_null_offset(self, selector: Optional[str] = None) -> float:
        """CALCulate:NULL:OFFSet? で NULL 機能の相対値を取得する。"""
        if selector is None:
            return self.query_float("CALCulate:NULL:OFFSet?")
        return self.query_float(f"CALCulate:NULL:OFFSet? {selector}")

    def set_calc_state(self, enabled: bool) -> None:
        """CALCulate:STATe を設定する。

        XDM1000 マニュアル上は OFF のみが明示されている。ON はファーム依存の可能性が
        あるため、enabled=True は現在の CALC function を維持して ON する機種向けの
        低レベル escape hatch として送信だけ行う。
        """
        self.write(f"CALCulate:STATe {'ON' if enabled else 'OFF'}")

    def calc_off(self) -> None:
        """CALCulate:STATe OFF で数学機能を OFF にする。"""
        self.write("CALCulate:STATe OFF")

    # ------------------------------------------------------------------
    # Other commands
    # ------------------------------------------------------------------

    def auto(self) -> None:
        """AUTO で autoscale を有効にする。"""
        self.write("AUTO")

    def get_auto(self) -> bool:
        """AUTO? で autoscale 状態を取得する。"""
        return self.query_bool("AUTO?")

    def set_range(self, range_index: Union[int, str]) -> None:
        """RANGE で現在の測定機能に対してレンジ番号または DEF を設定する。"""
        self.write(f"RANGE {range_index}")

    def get_range(self) -> int:
        """RANGE? で現在のレンジ番号を取得する。

        マニュアルの構文表には query が明示されていないが、実機/ファームの差分確認用に
        ドライバ層では実装しておく。未対応ファームでは TimeoutError になる。
        """
        return self.query_int("RANGE?")

    def set_rate(self, speed: str) -> None:
        """RATE で測定速度を設定する。F, M, S を想定する。"""
        self.write(f"RATE {speed}")

    def get_rate(self) -> str:
        """RATE? で測定速度を取得する。"""
        return self.query("RATE?")

    def measure_raw(self) -> str:
        """MEAS? の応答を文字列のまま返す。"""
        return self.query("MEAS?")

    def measure(self) -> MeasureValue:
        """MEAS? の応答を数値化して返す。副表示ありの場合は 2 要素 tuple を返す。"""
        raw = self.measure_raw()
        values = [float(v.strip()) for v in raw.split(",")]
        if len(values) == 1:
            return values[0]
        if len(values) == 2:
            return values[0], values[1]
        raise ValueError(f"unexpected MEAS? response: {raw}")

    def measure_main(self) -> float:
        """MEAS1? で主表示の測定値を取得する。"""
        return self.query_float("MEAS1?")

    def measure_sub(self) -> float:
        """MEAS2? で副表示の測定値を取得する。"""
        return self.query_float("MEAS2?")

    # ------------------------------------------------------------------
    # Small convenience aliases within low-level layer
    # ------------------------------------------------------------------

    def sleep_after_configure(self, seconds: float = 0.2) -> None:
        """設定直後の待ち時間を明示的に入れるための小補助である。"""
        time.sleep(seconds)


# 後方互換名である。既存コードが XDM1241 を import していても動くように残す。
XDM1241 = XDM1000SCPI



def _example_main() -> None:
    """SCPI ドライバ層だけを直接動かす最小サンプルである。

    この main は低レベル SCPI ドライバの動作確認用である。上位の測定シーケンス、
    running state、連続測定結果の保存は xdm1000_ctrl.py 側で扱う。

    実行例::

        python xdm1000_scpi.py /dev/cu.usbserial-140

    ここでは DC 電圧へ切り替え、速度 F で MEAS1? を数回読む。
    """
    import argparse

    parser = argparse.ArgumentParser(description="XDM1000 SCPI 直接操作サンプル")
    parser.add_argument("port", help="例: /dev/cu.usbserial-140")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--kind", default="voltage_dc", choices=[
        "voltage_dc", "voltage_ac", "current_dc", "current_ac",
        "resistance", "fresistance", "frequency", "period", "capacitance",
        "temperature_rtd", "diode", "continuity",
    ])
    parser.add_argument("--range", dest="range_value", default="AUTO")
    parser.add_argument("--rate", default="F", help="F, M, S")
    args = parser.parse_args()

    with XDM1000SCPI(port=args.port, baudrate=args.baudrate, timeout=args.timeout) as dmm:
        print("IDN:", dmm.idn())
        dmm.remote()
        try:
            if args.kind == "voltage_dc":
                dmm.configure_voltage_dc(args.range_value)
            elif args.kind == "voltage_ac":
                dmm.configure_voltage_ac(args.range_value)
            elif args.kind == "current_dc":
                dmm.configure_current_dc(args.range_value)
            elif args.kind == "current_ac":
                dmm.configure_current_ac(args.range_value)
            elif args.kind == "resistance":
                dmm.configure_resistance(args.range_value)
            elif args.kind == "fresistance":
                dmm.configure_fresistance(args.range_value)
            elif args.kind == "frequency":
                dmm.configure_frequency()
            elif args.kind == "period":
                dmm.configure_period()
            elif args.kind == "capacitance":
                dmm.configure_capacitance(args.range_value)
            elif args.kind == "temperature_rtd":
                dmm.configure_temperature_rtd()
            elif args.kind == "diode":
                dmm.configure_diode()
            elif args.kind == "continuity":
                dmm.configure_continuity()
            else:
                raise ValueError(args.kind)

            dmm.set_rate(args.rate)
            dmm.sleep_after_configure(0.2)

            for i in range(args.count):
                value = dmm.measure_main()
                print(f"{i}: {value}")
                time.sleep(args.interval)
        finally:
            dmm.local()


if __name__ == "__main__":
    _example_main()
