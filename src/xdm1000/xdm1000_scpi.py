#!/usr/bin/env python3
"""Low-level SCPI driver for OWON XDM1000 series digital multimeters.

This module intentionally stays close to the SCPI command layer.
High-level measurement orchestration must be implemented in xdm1000_ctrl.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import serial


ScpiValue = str | int | float


@dataclass(frozen=True)
class AverageStats:
    """Statistics returned by CALCulate:AVERage:ALL?."""

    minimum: float
    maximum: float
    average: float
    count: int


class XDM1000SCPI:
    """Low-level SCPI wrapper for XDM1000/XDM1241.

    The class owns a serial port and exposes SCPI-level commands.
    It does not implement long-running measurement state, locking, or buffering.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: float = 2.0,
        write_timeout: float | None = 2.0,
        terminator: str = "\n",
        encoding: str = "ascii",
        **serial_kwargs: Any,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.terminator = terminator
        self.encoding = encoding
        self._serial_kwargs = dict(serial_kwargs)
        self._ser: serial.Serial | None = None
        self.open()

    def open(self) -> None:
        """Open the serial port if it is not open."""
        if self._ser is not None and self._ser.is_open:
            return
        self._ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            write_timeout=self.write_timeout,
            **self._serial_kwargs,
        )

    def close(self) -> None:
        """Close the serial port."""
        if self._ser is not None:
            self._ser.close()
            self._ser = None

    @property
    def is_open(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def _require_open(self) -> serial.Serial:
        if self._ser is None or not self._ser.is_open:
            raise RuntimeError("Serial port is not open.")
        return self._ser

    def write(self, command: str) -> None:
        """Send a raw SCPI command."""
        ser = self._require_open()
        data = (command + self.terminator).encode(self.encoding)
        ser.write(data)
        ser.flush()

    def query(self, command: str) -> str:
        """Send a raw SCPI query and return a stripped string response."""
        ser = self._require_open()
        self.write(command)
        line = ser.readline()
        return line.decode(self.encoding, errors="replace").strip()

    def query_float(self, command: str) -> float:
        return float(self.query(command))

    def query_int(self, command: str) -> int:
        return int(float(self.query(command)))

    def query_bool(self, command: str) -> bool:
        text = self.query(command).strip().upper()
        return text in {"1", "ON", "TRUE"}

    @staticmethod
    def _fmt(value: ScpiValue) -> str:
        if isinstance(value, str):
            return value
        return repr(value)

    # ------------------------------------------------------------------
    # IEEE 488.2 common commands
    # ------------------------------------------------------------------
    def idn(self) -> str:
        return self.query("*IDN?")

    def reset(self) -> None:
        self.write("*RST")

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------
    def remote(self) -> None:
        self.write("SYSTem:REMote")

    def local(self) -> None:
        self.write("SYSTem:LOCal")

    def set_beeper(self, enabled: bool) -> None:
        self.write(f"SYSTem:BEEPer {'ON' if enabled else 'OFF'}")

    def get_beeper(self) -> bool:
        return self.query_bool("SYSTem:BEEPer?")

    # ------------------------------------------------------------------
    # Sense / function selection
    # ------------------------------------------------------------------
    def set_function(self, function: str) -> None:
        self.write(f"SENSe:FUNCtion {function}")

    def get_function(self) -> str:
        return self.query("SENSe:FUNCtion?")

    def set_main_function(self, function: str) -> None:
        self.write(f"SENSe:FUNCtion1 {function}")

    def get_main_function(self) -> str:
        return self.query("SENSe:FUNCtion1?")

    def set_sub_function(self, function: str) -> None:
        self.write(f"SENSe:FUNCtion2 {function}")

    def get_sub_function(self) -> str:
        return self.query("SENSe:FUNCtion2?")

    def set_range(self, value: ScpiValue) -> None:
        self.write(f"SENSe:RANGe {self._fmt(value)}")

    def get_range(self) -> str:
        return self.query("SENSe:RANGe?")

    def auto(self) -> None:
        self.write("SENSe:AUTO")

    def get_auto(self) -> str:
        return self.query("SENSe:AUTO?")

    def set_rate(self, rate: str) -> None:
        """Set measurement rate: F, M, or S."""
        self.write(f"SENSe:RATE {rate}")

    def get_rate(self) -> str:
        return self.query("SENSe:RATE?")

    # ------------------------------------------------------------------
    # Configure
    # ------------------------------------------------------------------
    def configure_voltage_dc(self, range_value: ScpiValue = "AUTO") -> None:
        self.write(f"CONFigure:VOLTage:DC {self._fmt(range_value)}")

    def configure_voltage_ac(self, range_value: ScpiValue = "AUTO") -> None:
        self.write(f"CONFigure:VOLTage:AC {self._fmt(range_value)}")

    def configure_current_dc(self, range_value: ScpiValue = "AUTO") -> None:
        self.write(f"CONFigure:CURRent:DC {self._fmt(range_value)}")

    def configure_current_ac(self, range_value: ScpiValue = "AUTO") -> None:
        self.write(f"CONFigure:CURRent:AC {self._fmt(range_value)}")

    def configure_resistance(self, range_value: ScpiValue = "AUTO") -> None:
        self.write(f"CONFigure:RESistance {self._fmt(range_value)}")

    def configure_fresistance(self, range_value: ScpiValue = "AUTO") -> None:
        self.write(f"CONFigure:FRESistance {self._fmt(range_value)}")

    def configure_frequency(self, range_value: ScpiValue = "AUTO") -> None:
        self.write(f"CONFigure:FREQuency {self._fmt(range_value)}")

    def configure_period(self, range_value: ScpiValue = "AUTO") -> None:
        self.write(f"CONFigure:PERiod {self._fmt(range_value)}")

    def configure_capacitance(self, range_value: ScpiValue = "AUTO") -> None:
        self.write(f"CONFigure:CAPacitance {self._fmt(range_value)}")

    def configure_temperature_rtd(self, rtd_type: str | None = None) -> None:
        if rtd_type is None:
            self.write("CONFigure:TEMPerature:RTD")
        else:
            self.write(f"CONFigure:TEMPerature:RTD {rtd_type}")

    def configure_diode(self) -> None:
        self.write("CONFigure:DIODe")

    def configure_continuity(self) -> None:
        self.write("CONFigure:CONTinuity")

    # ------------------------------------------------------------------
    # Temperature / continuity options
    # ------------------------------------------------------------------
    def set_temperature_rtd_type(self, rtd_type: str) -> None:
        self.write(f"SENSe:TEMPerature:RTD:TYPE {rtd_type}")

    def get_temperature_rtd_type(self) -> str:
        return self.query("SENSe:TEMPerature:RTD:TYPE?")

    def set_temperature_unit(self, unit: str) -> None:
        self.write(f"SENSe:TEMPerature:UNIT {unit}")

    def get_temperature_unit(self) -> str:
        return self.query("SENSe:TEMPerature:UNIT?")

    def set_temperature_show(self, show: str) -> None:
        self.write(f"SENSe:TEMPerature:SHOW {show}")

    def get_temperature_show(self) -> str:
        return self.query("SENSe:TEMPerature:SHOW?")

    def set_continuity_threshold(self, resistance_ohm: ScpiValue) -> None:
        self.write(f"SENSe:CONTinuity:THREshold {self._fmt(resistance_ohm)}")

    def get_continuity_threshold(self) -> float:
        return self.query_float("SENSe:CONTinuity:THREshold?")

    # ------------------------------------------------------------------
    # CALC / statistics
    # ------------------------------------------------------------------
    def set_calc_function(self, function: str) -> None:
        self.write(f"CALCulate:FUNCtion {function}")

    def get_calc_function(self) -> str:
        return self.query("CALCulate:FUNCtion?")

    def calc_off(self) -> None:
        self.write("CALCulate:STATe OFF")

    def set_calc_state(self, enabled: bool) -> None:
        """Set CALC state when supported by the instrument firmware."""
        self.write(f"CALCulate:STATe {'ON' if enabled else 'OFF'}")

    def get_average_all_raw(self) -> str:
        return self.query("CALCulate:AVERage:ALL?")

    def get_average_all(self) -> AverageStats:
        raw = self.get_average_all_raw()
        parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
        if len(parts) < 4:
            raise ValueError(f"Unexpected CALCulate:AVERage:ALL? response: {raw!r}")
        return AverageStats(
            minimum=float(parts[0]),
            maximum=float(parts[1]),
            average=float(parts[2]),
            count=int(float(parts[3])),
        )

    def get_average(self) -> float:
        return self.query_float("CALCulate:AVERage:AVERage?")

    def get_average_maximum(self) -> float:
        return self.query_float("CALCulate:AVERage:MAXimum?")

    def get_average_minimum(self) -> float:
        return self.query_float("CALCulate:AVERage:MINimum?")

    def set_db_reference(self, value: ScpiValue) -> None:
        self.write(f"CALCulate:DB:REFerence {self._fmt(value)}")

    def get_db_reference(self) -> float:
        return self.query_float("CALCulate:DB:REFerence?")

    def set_dbm_reference(self, value: ScpiValue) -> None:
        self.write(f"CALCulate:DBM:REFerence {self._fmt(value)}")

    def get_dbm_reference(self) -> float:
        return self.query_float("CALCulate:DBM:REFerence?")

    def set_null_offset(self, value: ScpiValue) -> None:
        self.write(f"CALCulate:NULL:OFFSet {self._fmt(value)}")

    def get_null_offset(self) -> float:
        return self.query_float("CALCulate:NULL:OFFSet?")

    # ------------------------------------------------------------------
    # Measurement readout
    # ------------------------------------------------------------------
    def measure_raw(self) -> str:
        return self.query("MEAS?")

    def measure(self) -> float | tuple[float, ...]:
        raw = self.measure_raw()
        values = tuple(float(x.strip()) for x in raw.split(",") if x.strip())
        if len(values) == 1:
            return values[0]
        return values

    def measure_main(self) -> float:
        return self.query_float("MEAS1?")

    def measure_sub(self) -> float:
        return self.query_float("MEAS2?")


XDM1241SCPI = XDM1000SCPI
