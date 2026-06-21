# FastAPI / ese774_frame 連携

`server_fastapi` は `Xdm1000Ctrl` を ese774_frame 経由で FastAPI に公開するための構成である。

SCPI ドライバを直接公開しない。

サーバー側で実体化される制御クラスは `Xdm1000Ctrl` である。

---
# 必要なもの

- [ese774_frame](https://github.com/ohara-lab-su/ese774_frame): スサノオプロジェクトで作成したフレーム
- [x_logger](https://github.com/ohara-lab-su/x_logger): ローガーならば何でも構わないが、スサノオプロジェクトのロガーを推奨する

---
# xdm1000 制御の基本構成

```text
xdm1000/server_fastapi/
├── xdm1000_ctrl.py
├── xdm1000_scpi.py
└── xdm1000_worker.py:
```

---
# xdm1000 Server の基本構成

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

`spec.py` は FastAPI に公開する API を定義する。
`Xdm1000Ctrl` の全メソッドを公開するのではなく、外部から使う意味がある API のみを公開する。

公開対象は主に次である。

- 状態取得
- One Shot 測定
- Continuous 測定
- Statistics 測定
- 結果取得
- 停止要求

低レベル SCPI API は公開しない。

---

# response_model

測定結果のように dict をそのまま返す API では `response_model=None` を用いる。
ese774_frame 側では戻り値を `value` に包む処理が存在するため、`DictResponse` を指定すると FastAPI の response validation で失敗する場合がある。
そのため、`meas_one_shot()` などの dict 返却 API は `response_model=None` とする。

---
# Router
Router は ese774_frame の `DeviceRouter` を継承する。

```python
from ese774_frame.routers.device_router import DeviceRouter


class Xdm1000Router(DeviceRouter):
    pass
```

Router 側に装置固有の実処理は書かない。
実処理は `Xdm1000Ctrl` に置く。

---
# Client

Client は ese774_frame の client を利用する。

同期 client は次である。

```python
from xdm1000.server_fastapi.clients.sync_xdm1000_client import SyncXdm1000Client
```

非同期 client は次である。

```python
from xdm1000.server_fastapi.clients.async_xdm1000_client import AsyncXdm1000Client
```

import は絶対 import を用いる。

---
# make.py

`make.py` は `.pyi` を生成するためのスクリプトである。
生成対象は次の三つである。

```text
clients/async_xdm1000_client.pyi
clients/sync_xdm1000_client.pyi
routers/xdm1000_router.pyi
```

余計な探索処理や fallback import は入れない。

ese774_frame の generator を直接 import して使う。

---

# サーバー起動

代表的な起動スクリプトは `examples/serve_start.py` である。

```python
#!/usr/bin/env python3
"""XDM1000 FastAPI サーバー起動例である。"""

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

# クライアント測定
代表的なクライアント測定例は `examples/client_meas_volt.py` である。

```python
#!/usr/bin/env python3
"""XDM1000 電圧測定サンプル"""

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

# API path

ese774_frame により、API は次の形式で公開される。

```text
POST /instance/xdm1000/<api_name>
```

例

```text
POST /instance/xdm1000/meas_one_shot
POST /instance/xdm1000/get_state
POST /instance/xdm1000/start_continuous_meas
```

---

# 注意事項

FastAPI サーバー側では `Xdm1000Ctrl` が実体化される。
`Xdm1000Ctrl.__init__()` は `logger`, `log_level`, `config` を受け取れる必要がある。
ese774_frame は device class 生成時にこれらを渡す。
`config` が渡された場合、`PORT`, `TIMEOUT`, `BAUDRATE` を参照できるようにする。

---
## 作者
- Kengo NAKADA
