# SCPI Driver API Reference

`xdm1000_scpi.py` provides the low-level SCPI API.

## AverageStats

A simple class holding the result of `CALCulate:AVERage:ALL?`.

```text
minimum
maximum
average
count
```

## Initializing Xdm1000Scpi

```python
Xdm1000Scpi(
    port,
    timeout=1.0,
    baudrate=115200,
    logger=None,
    logger_name=None,
    log_level=None,
    config=None,
)
```

When `config` is supplied, its `PORT`, `TIMEOUT`, `BAUDRATE`, and `LOGGER_LEVEL` values take precedence. If `port` remains unspecified, `ValueError` is raised.

## Lifecycle

### close()

Closes the serial port.

### disconnect()

Alias for `close()`.

### __del__()

On destruction, attempts `local()` and then `close()`.

## Basic Communication

### write(command)

Sends an SCPI command, appending LF if it does not already end with a newline.

### query(command)

Sends an SCPI query and returns one response line as a string. Clears the receive buffer before sending. Raises `TimeoutError` if the response is empty.

### query_float(command)

Converts the result of `query(command)` to `float`.

### query_int(command)

Converts the result of `query(command)` to `int` via `float`.

## IEEE 488.2

### idn()

Sends `*IDN?` and returns the identification string.

### reset()

Sends `*RST`.

## System

### remote()

Sends `SYSTem:REMote`.

### local()

Sends `SYSTem:LOCal`.

### set_beeper(enabled)

Sends `SYSTem:BEEPer:STATe ON/OFF`.

### get_beeper()

Queries `SYSTem:BEEPer:STATe?` and returns `True` for a nonzero response.

## Configure

### configure_voltage_dc(range_value="AUTO")

Sends `CONFigure:VOLTage:DC {range_value}`.

### configure_voltage_ac(range_value="AUTO")

Sends `CONFigure:VOLTage:AC {range_value}`.

### configure_current_dc(range_value="AUTO")

Sends `CONFigure:CURRent:DC {range_value}`.

### configure_current_ac(range_value="AUTO")

Sends `CONFigure:CURRent:AC {range_value}`.

### configure_resistance(range_value="AUTO")

Sends `CONFigure:RESistance {range_value}`.

### configure_fresistance(range_value="AUTO")

Sends `CONFigure:FRESistance {range_value}`.

### configure_frequency()

Sends `CONFigure:FREQuency`.

### configure_period()

Sends `CONFigure:PERiod`.

### configure_capacitance(range_value="AUTO")

Sends `CONFigure:CAPacitance {range_value}`.

### configure_temperature_rtd()

Sends `CONFigure:TEMPerature:RTD`.

### configure_diode()

Sends `CONFigure:DIODe`.

### configure_continuity()

Sends `CONFigure:CONTinuity`.

## CALCulate

### set_calc_function_average()

Sends `CALCulate:FUNCtion AVERage`.

### get_average_all()

Queries `CALCulate:AVERage:ALL?` and returns the four response values as `AverageStats`. Raises `ValueError` if the response does not have exactly four elements.

## RATE

### set_rate(speed)

Sends `RATE {speed}`. The implementation does not validate the value; the ctrl layer validates `F/M/S` in `set_integration_speed()`.

### get_rate()

Returns the string response to `RATE?`.

## Measure

### meas_raw()

Returns the raw string response to `MEAS?`.

### meas()

Converts the comma-separated response to `MEAS?` into floats. Returns a `float` for one value, or a `(main, sub)` tuple for two; otherwise raises `ValueError`.

### meas_main()

Returns `MEAS1?` as a float.

### meas_sub()

Returns `MEAS2?` as a float.
