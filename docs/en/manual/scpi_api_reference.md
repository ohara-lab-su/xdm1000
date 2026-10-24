[![en](https://img.shields.io/badge/lang-en-red.svg)](https://ohara-lab-su.github.io/xdm1000/en/manual/scpi_api_reference.html) [![ja](https://img.shields.io/badge/lang-ja-blue.svg)](https://ohara-lab-su.github.io/xdm1000/ja/manual/scpi_api_reference.html)

# SCPI Driver API Reference

`Xdm1000Scpi` is the low-level driver. It exposes serial transport, IEEE 488.2 commands, system operations, configuration, measurement and statistics queries. This reference lists the methods and their signatures as documented in the supplied Japanese source. The high-level controller should be preferred for instrument-oriented workflows.

> **Documentation scope:** This English guide is an abridged technical companion to the complete Japanese manual. This page is a summary of the supplied Japanese document; consult the Japanese version for details and complete examples.

## Average statistics

```text
minimum
maximum
average
count
```

## Driver initialization

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

## Lifecycle

### close()

### disconnect()

### __del__()

## Close

### write(command)

### query(command)

### query_float(command)

### query_int(command)

## Disconnect

### idn()

### reset()

## Destructor

### remote()

### local()

### set_beeper(enabled)

### get_beeper()

## Communication

### configure_voltage_dc(range_value="AUTO")

### configure_voltage_ac(range_value="AUTO")

### configure_current_dc(range_value="AUTO")

### configure_current_ac(range_value="AUTO")

### configure_resistance(range_value="AUTO")

### configure_fresistance(range_value="AUTO")

### configure_frequency()

### configure_period()

### configure_capacitance(range_value="AUTO")

### configure_temperature_rtd()

### configure_diode()

### configure_continuity()

## Write

### set_calc_function_average()

### get_average_all()

## Query

### set_rate(speed)

### get_rate()

## Float query

### meas_raw()

### meas()

### meas_main()

### meas_sub()
