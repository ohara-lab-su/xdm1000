[![en](https://img.shields.io/badge/lang-en-red.svg)](https://ohara-lab-su.github.io/xdm1000/en/manual/scpi_layer_overview.html) [![ja](https://img.shields.io/badge/lang-ja-blue.svg)](https://ohara-lab-su.github.io/xdm1000/ja/manual/scpi_layer_overview.html)

# SCPI Driver Overview

`xdm1000_scpi.py` wraps ASCII SCPI commands over a pyserial connection configured as 8-N-1 with no flow control. It implements `write`, `query`, typed query helpers, identification, reset, measurement configuration and data retrieval. It does not manage long-running acquisition or controller state. The controller's primary measurement reads `MEAS1?` via `meas_main()`.

> **Documentation scope:** This English guide is an abridged technical companion to the complete Japanese manual. This page is a summary of the supplied Japanese document; consult the Japanese version for details and complete examples.

## Responsibilities

## Serial communication

```python
serial.Serial(
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
```

## Relationship with the controller
