# XDM1000 / XDM1241 Hardware Capabilities and ctrl API Mapping

This document summarizes the hardware capabilities that are relevant to the `xdm1000_ctrl.py` high-level API. The low-level SCPI layer should remain a plain wrapper around the instrument commands. Hardware-specific interpretation, unit handling, and discrete range validation are handled in the ctrl layer.

## Design rule

The XDM1000 programming manual defines measurement ranges as discrete `RANGE` indices. Those indices are not physical values. For example, in DC voltage mode, `RANGE 3` means the 5 V range. In AC voltage mode, `RANGE 3` means the 50 V range.

Therefore, the high-level ctrl API separates two operations.

`set_range(value)` sets a manual range by physical quantity. The ctrl layer converts the physical value to the correct SCPI `RANGE` index for the current measurement mode.

`set_range_index(index)` sets a manual range by the explicit SCPI `RANGE` index. This is a low-level escape hatch for users who are reading the programming manual directly.

The SCPI layer remains plain. It receives only the final `RANGE <index>` value.

## Basic measurement sequence

A normal measurement should be configured in this order.

1. Select the measurement mode with `set_mode(mode)`.
2. Select either automatic range with `set_auto_range(True)` or manual range with `set_range(value)`.
3. Select the internal measurement speed with `set_integration_speed(speed)` if needed.
4. Read one value with `meas()` or start repeated reads with `meas_continue()`.

Example for DC voltage with the 5 V range:

```python
from xdm1000.xdm1000_ctrl import Xdm1000Ctrl

dmm = Xdm1000Ctrl(port="/dev/cu.usbserial-10", use_process=False)
dmm.set_mode("voltage_dc")
dmm.set_range(5.0)
dmm.set_integration_speed("M")
result = dmm.meas()
```

The call `set_range(5.0)` means 5 V because the current mode is `voltage_dc`. The ctrl layer converts it to `RANGE 3` internally.

The equivalent explicit-index form is:

```python
dmm.set_mode("voltage_dc")
dmm.set_range_index(3)
```

## Measurement modes

| ctrl mode | SCPI function | Manual range support |
|---|---|---|
| `voltage_dc` | `FUNCtion "VOLT"` | Yes |
| `voltage_ac` | `FUNCtion "VOLT AC"` | Yes |
| `current_dc` | `FUNCtion "CURR"` | Yes |
| `current_ac` | `FUNCtion "CURR AC"` | Yes |
| `resistance` | `FUNCtion "RES"` | Yes |
| `fresistance` | `FUNCtion "FRES"` | Yes, same range table as resistance |
| `frequency` | `FUNCtion "FREQ"` | No ctrl manual range table |
| `period` | `FUNCtion "PER"` | No ctrl manual range table |
| `capacitance` | `FUNCtion "CAP"` | Yes |
| `temperature_rtd` | `FUNCtion "TEMP"` | Yes, sensor selection |
| `diode` | `FUNCtion "DIOD"` | No ctrl manual range table |
| `continuity` | `FUNCtion "CONT"` | No ctrl manual range table |

## DC voltage ranges

Mode: `voltage_dc`

Unit for numeric `set_range(value)`: V

| Hardware range | Physical value for `set_range()` | Explicit SCPI index for `set_range_index()` |
|---:|---:|---:|
| 50 mV | `0.05` or `"50 mV"` | `1` |
| 500 mV | `0.5` or `"500 mV"` | `2` |
| 5 V | `5.0` or `"5 V"` | `3` |
| 50 V | `50.0` or `"50 V"` | `4` |
| 500 V | `500.0` or `"500 V"` | `5` |
| 1000 V | `1000.0` or `"1000 V"` | `6` |

## AC voltage ranges

Mode: `voltage_ac`

Unit for numeric `set_range(value)`: V

| Hardware range | Physical value for `set_range()` | Explicit SCPI index for `set_range_index()` |
|---:|---:|---:|
| 500 mV | `0.5` or `"500 mV"` | `1` |
| 5 V | `5.0` or `"5 V"` | `2` |
| 50 V | `50.0` or `"50 V"` | `3` |
| 500 V | `500.0` or `"500 V"` | `4` |
| 750 V | `750.0` or `"750 V"` | `5` |

## DC current ranges

Mode: `current_dc`

Unit for numeric `set_range(value)`: A

| Hardware range | Physical value for `set_range()` | Explicit SCPI index for `set_range_index()` |
|---:|---:|---:|
| 500 uA | `0.0005` or `"500 uA"` | `1` |
| 5 mA | `0.005` or `"5 mA"` | `2` |
| 50 mA | `0.05` or `"50 mA"` | `3` |
| 500 mA | `0.5` or `"500 mA"` | `4` |
| 5 A | `5.0` or `"5 A"` | `5` |
| 10 A | `10.0` or `"10 A"` | `6` |

## AC current ranges

Mode: `current_ac`

Unit for numeric `set_range(value)`: A

| Hardware range | Physical value for `set_range()` | Explicit SCPI index for `set_range_index()` |
|---:|---:|---:|
| 500 uA | `0.0005` or `"500 uA"` | `1` |
| 5 mA | `0.005` or `"5 mA"` | `2` |
| 50 mA | `0.05` or `"50 mA"` | `3` |
| 500 mA | `0.5` or `"500 mA"` | `4` |
| 5 A | `5.0` or `"5 A"` | `5` |
| 10 A | `10.0` or `"10 A"` | `6` |

## Resistance ranges

Modes: `resistance`, `fresistance`

Unit for numeric `set_range(value)`: Ohm

| Hardware range | Physical value for `set_range()` | Explicit SCPI index for `set_range_index()` |
|---:|---:|---:|
| 500 Ohm | `500.0` or `"500 Ohm"` | `1` |
| 5 kOhm | `5000.0` or `"5 kOhm"` | `2` |
| 50 kOhm | `50000.0` or `"50 kOhm"` | `3` |
| 500 kOhm | `500000.0` or `"500 kOhm"` | `4` |
| 5 MOhm | `5000000.0` or `"5 MOhm"` | `5` |
| 50 MOhm | `50000000.0` or `"50 MOhm"` | `6` |

## Capacitance ranges

Mode: `capacitance`

Unit for numeric `set_range(value)`: F

| Hardware range | Physical value for `set_range()` | Explicit SCPI index for `set_range_index()` |
|---:|---:|---:|
| 50 nF | `50e-9` or `"50 nF"` | `1` |
| 500 nF | `500e-9` or `"500 nF"` | `2` |
| 5 uF | `5e-6` or `"5 uF"` | `3` |
| 50 uF | `50e-6` or `"50 uF"` | `4` |
| 500 uF | `500e-6` or `"500 uF"` | `5` |
| 5 mF | `5e-3` or `"5 mF"` | `6` |
| 50 mF | `50e-3` or `"50 mF"` | `7` |

## Temperature sensor selection

Mode: `temperature_rtd`

Temperature mode does not use a continuous physical range value. It selects the sensor table.

| Hardware option | Value for `set_range()` | Explicit SCPI index for `set_range_index()` |
|---|---|---:|
| KITS90 | `"KITS90"` | `1` |
| PT100 | `"PT100"` | `2` |

## Measurement speed

The instrument supports three internal measurement speed settings. The ctrl method is `set_integration_speed(speed)`. The name is kept for API compatibility, but the actual SCPI command is `RATE`.

| ctrl value | SCPI value | Hardware speed | Approximate internal reading time | Practical note |
|---|---|---:|---:|---|
| `"F"` | `RATE F` | 65 readings/s | 15.4 ms | Useful for monitoring faster changes. SCPI readout rate from Python is not guaranteed. |
| `"M"` | `RATE M` | 16 readings/s | 62.5 ms | Practical default for stable Python readout. |
| `"S"` | `RATE S` | 4 readings/s | 250 ms | Useful for lower-noise or stable-value measurements. |

The speed setting is an internal measurement setting of the meter. It does not guarantee that a Python loop using `MEAS1?` can collect data at the same rate.

## Automatic range

`set_auto_range(True)` sends the instrument `AUTO` command through the SCPI layer.

`set_auto_range(False)` does not send a generic `AUTO OFF` command because the programming manual does not define such a universal command. It re-applies the last validated manual range index. Therefore, a manual range must be set first.

Valid sequence:

```python
dmm.set_mode("voltage_dc")
dmm.set_range("5 V")
dmm.set_auto_range(False)
```

Invalid sequence:

```python
dmm.set_mode("voltage_dc")
dmm.set_auto_range(False)
```

## Result metadata

After the ctrl-layer change, measurement results include both the user-facing range value and the SCPI range index when the direct ctrl path is used.

`range_value` records the user request passed to `set_range(value)`.

`range_index` records the discrete SCPI `RANGE` index sent to the instrument.

`range_label` records the human-readable hardware range label, such as `5 V` or `500 mA`.

## Recommended examples

DC voltage, 5 V range:

```python
dmm.set_mode("voltage_dc")
dmm.set_range("5 V")
dmm.set_integration_speed("M")
value = dmm.meas()
```

DC current, 5 mA range:

```python
dmm.set_mode("current_dc")
dmm.set_range("5 mA")
dmm.set_integration_speed("M")
value = dmm.meas()
```

Resistance, 50 kOhm range:

```python
dmm.set_mode("resistance")
dmm.set_range("50 kOhm")
value = dmm.meas()
```

Capacitance, 5 uF range:

```python
dmm.set_mode("capacitance")
dmm.set_range("5 uF")
value = dmm.meas()
```

Explicit SCPI index, DC voltage 5 V range:

```python
dmm.set_mode("voltage_dc")
dmm.set_range_index(3)
value = dmm.meas()
```

This explicit-index form should be used only when the caller intentionally works with the XDM1000 programming manual's discrete `RANGE` indices.
