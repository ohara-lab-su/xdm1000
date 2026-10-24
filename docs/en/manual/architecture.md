[![en](https://img.shields.io/badge/lang-en-red.svg)](https://ohara-lab-su.github.io/xdm1000/en/manual/architecture.html) [![ja](https://img.shields.io/badge/lang-ja-blue.svg)](https://ohara-lab-su.github.io/xdm1000/ja/manual/architecture.html)

# System Architecture

The OWON XDM1000/XDM1241 integration separates the low-level SCPI driver, high-level instrument control, optional worker process, and FastAPI/ese774_frame transport. The controller can operate in the current process or delegate instrument I/O to a child process. The FastAPI layer publishes selected controller operations without making the controller depend on FastAPI.

> **Documentation scope:** This English guide is an abridged technical companion to the complete Japanese manual. This page is a summary of the supplied Japanese document; consult the Japanese version for details and complete examples.

## File layout

```text
xdm1000/
├── config.py
├── xdm1000_scpi.py
├── xdm1000_ctrl.py
├── xdm1000_worker.py
└── server_fastapi/
    ├── spec.py
    ├── models/
    │   └── common.py
    ├── routers/
    │   └── xdm1000_router.py
    └── clients/
        ├── sync_xdm1000_client.py
        └── async_xdm1000_client.py
```

## Layer structure

```text
User code / example
        │
        ▼
Xdm1000Ctrl
        │
        ├── use_process=False
        │       └── Xdm1000Scpi を同一プロセスで直接使用
        │
        └── use_process=True
                ├── Parent Process
                │   ├── command queue
                │   ├── response queue
                │   ├── shared state
                │   ├── result store
                │   └── stop event
                │
                └── Worker Process
                    └── Xdm1000Scpi
                        └── pyserial.Serial
```

## Local usage

```python
from xdm1000.xdm1000_ctrl import Xdm1000Ctrl


dmm = Xdm1000Ctrl(port="/dev/cu.usbserial-10", use_process=True)
try:
    print(dmm.idn())
    result = dmm.meas_voltage_dc()
    print(result)
finally:
    dmm.close()
```

## Direct SCPI usage

```python
from xdm1000.xdm1000_scpi import Xdm1000Scpi


dmm = Xdm1000Scpi(port="/dev/cu.usbserial-10")
try:
    print(dmm.idn())
    dmm.configure_voltage_dc("AUTO")
    dmm.set_rate("F")
    print(dmm.meas_main())
finally:
    dmm.close()
```

## FastAPI usage

## Configuration

```yaml
PORT: "/dev/cu.usbserial-10"
BAUDRATE: 115200
TIMEOUT: 2.0
LOGGER_LEVEL: "debug"
SERVER_HOST: "127.0.0.1"
SERVER_PORT: 8000
```
