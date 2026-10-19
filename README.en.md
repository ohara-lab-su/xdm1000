# FastAPI / ese774_frame Integration

[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/ohara-lab-su/xdm1000-py/blob/main/README.en.md)
[![ja](https://img.shields.io/badge/lang-ja-yellow.svg)](https://github.com/ohara-lab-su/xdm1000-py/blob/main/README.md)

`server_fastapi` provides a way to expose `Xdm1000Ctrl` through FastAPI using ese774_frame.

The SCPI driver is not exposed directly.

The control class instantiated on the server is `Xdm1000Ctrl`.

---

# Requirements

- [ese774_frame](https://github.com/ohara-lab-su/ese774_frame): A framework developed for the Susanoo Project.
- [x_logger](https://github.com/ohara-lab-su/x_logger): Any logger may be used, but the logger developed for the Susanoo
  Project is recommended.

---

# Basic Structure of XDM1000 Control

```text
xdm1000/server_fastapi/
├── xdm1000_ctrl.py
├── xdm1000_scpi.py
└── xdm1000_worker.py:
```

---

# Basic Structure of the XDM1000 Server

```text
xdm1000/server_fastapi/
├── spec.py
├── make.py
├── models/
│   └── common.py
├── routers/
│   ├── __init__.py
│   └── xdm1000_router.py
└── clients/
    ├── __init__.py
    ├── sync_xdm1000_client.py
    └── async_xdm1000_client.py
```

---

# spec.py

`spec.py` defines the APIs exposed through FastAPI.
Rather than exposing every method of `Xdm1000Ctrl`, only APIs that are meaningful for external use are exposed.

These mainly include:

- Retrieving device state
- One-shot measurements
- Continuous measurements
- Statistics measurements
- Retrieving results
- Stop requests

Low-level SCPI APIs are not exposed.

---

# response_model

Use `response_model=None` for APIs that directly return a dictionary, such as measurement results.
Because ese774_frame includes logic that wraps return values in `value`, specifying `DictResponse` may cause FastAPI
response validation to fail.
Therefore, APIs returning dictionaries, such as `meas_one_shot()`, should use `response_model=None`.

---

# Router

The router inherits from ese774_frame's `DeviceRouter`.

```python
from ese774_frame.routers.device_router import DeviceRouter


class Xdm1000Router(DeviceRouter):
    pass
```

Do not implement device-specific operations in the router.
The actual operations belong in `Xdm1000Ctrl`.

---

# Client

The clients provided by ese774_frame are used.

The synchronous client is imported as follows:

```python
from xdm1000.server_fastapi.clients.sync_xdm1000_client import SyncXdm1000Client
```

The asynchronous client is imported as follows:

```python
from xdm1000.server_fastapi.clients.async_xdm1000_client import AsyncXdm1000Client
```

Use absolute imports.

---

# make.py

`make.py` is a script for generating `.pyi` files.
It generates the following three files:

```text
clients/async_xdm1000_client.pyi
clients/sync_xdm1000_client.pyi
routers/xdm1000_router.pyi
```

Do not add unnecessary discovery logic or fallback imports.

Import and use the generators from ese774_frame directly.

---

# Starting the Server

A representative startup script is `examples/serve_start.py`.

```python
#!/usr/bin/env python3
"""Example of starting the XDM1000 FastAPI server."""

from types import SimpleNamespace

from ese774_frame.api_server import FastApiServer
from x_logger import XLogger

from xdm1000.xdm1000_ctrl import Xdm1000Ctrl
from xdm1000.server_fastapi.spec import xdm1000_api_spec
from xdm1000.server_fastapi.routers.xdm1000_router import Xdm1000Router

PORT = "/dev/cu.usbserial-10"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000


def main() -> None:
    logger = XLogger(
        log_level="debug",
        logger_name="xdm1000.server",
        log_mode="rotate",
        log_name="xdm1000_server.log",
    )

    config = SimpleNamespace(
        PORT=PORT,
        SERVER_HOST=SERVER_HOST,
        SERVER_PORT=SERVER_PORT,
    )

    server = FastApiServer(
        device_cls=Xdm1000Ctrl,
        router_cls=Xdm1000Router,
        config=config,
        api_spec=xdm1000_api_spec,
        device_kwargs={"port": PORT},
        logger=logger,
        logger_name="xdm1000.server",
        lifespan_msg_prefix="XDM1000",
    )

    server.run(
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
```

---

# Client Measurement

A representative client measurement example is `examples/client_meas_volt.py`.

```python
#!/usr/bin/env python3
"""Example of measuring voltage with the XDM1000."""

from xdm1000.server_fastapi.clients.sync_xdm1000_client import SyncXdm1000Client

HOST = "127.0.0.1"
PORT = 8000


def main():
    dmm = SyncXdm1000Client(HOST, PORT)

    print(dmm.meas_one_shot("voltage_dc"))


if __name__ == "__main__":
    main()
```

---

# API Paths

ese774_frame exposes APIs using the following path format:

```text
POST /instance/xdm1000/<api_name>
```

Examples:

```text
POST /instance/xdm1000/meas_one_shot
POST /instance/xdm1000/get_state
POST /instance/xdm1000/start_continuous_meas
```

---

# Notes

The FastAPI server instantiates `Xdm1000Ctrl`.
`Xdm1000Ctrl.__init__()` must accept `logger`, `log_level`, and `config`.
ese774_frame passes these arguments when creating the device class.
When `config` is provided, `PORT`, `TIMEOUT`, and `BAUDRATE` must be accessible from it.

---

## Author

- Kengo NAKADA
