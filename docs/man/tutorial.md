# XDM1000 サーバー起動およびクライアント測定チュートリアル

本ページでは、XDM1000 を FastAPI サーバーとして起動し、クライアント側から `DeviceProxy` を用いて電圧を 1 回測定する最小構成を示す。

本チュートリアルは現在の `Xdm1000Ctrl` API に合わせている。旧 API である `meas_one_shot()`、`start_continuous_meas()`、`get_continuous_result()` は使用しない。

## 前提

本チュートリアルでは、次の構成を前提とする。

- XDM1000 / XDM1241 は USB シリアル経由で接続されている。
- シリアルポートは `/dev/cu.usbserial-10` である。
- サーバーは `127.0.0.1:8000` で起動する。
- クライアントは `ese774_frame.DeviceProxy` 経由で `Xdm1000Ctrl` に接続する。

シリアルポート名は環境により変わるため、実機環境に合わせて `PORT` または設定ファイルを修正すること。

## 設定ファイル

`xdm1000.yml` を作成する。

```yaml
# XDM1000 用設定例
SERVER_HOST: "127.0.0.1"
SERVER_PORT: 8000
CLIENT_LOGGER_NAME: "xdm1000_client"
SERVER_LOGGER_NAME: "xdm1000_server"

PORT: "/dev/cu.usbserial-10"
BAUDRATE: 115200
TIMEOUT: 2.0

LOGGER_LEVEL: "debug"
```

`Xdm1000Ctrl` は `config` が渡された場合、`PORT`、`TIMEOUT`、`BAUDRATE` をコンストラクタ引数より優先する。

## サーバー起動スクリプト

次の内容で `server_xdm1000.py` を作成する。

```python
#!/usr/bin/env python3
"""XDM1000 FastAPI サーバー起動例である。"""

from __future__ import annotations

from types import SimpleNamespace

from ese774_frame import FastApiServer
from x_logger import XLogger

from xdm1000.xdm1000_ctrl import Xdm1000Ctrl
from xdm1000.server_fastapi.spec import xdm1000_api_spec
from xdm1000.server_fastapi.routers.xdm1000_router import Xdm1000Router


PORT = "/dev/cu.usbserial-10"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000


def main() -> None:
    """XDM1000 をサーバー側デバイスクラスとして起動する。"""
    config = SimpleNamespace(
        PORT=PORT,
        BAUDRATE=115200,
        TIMEOUT=2.0,
        SERVER_HOST=SERVER_HOST,
        SERVER_PORT=SERVER_PORT,
        SERVER_LOGGER_NAME="xdm1000.server",
    )

    logger = XLogger(
        log_level="debug",
        logger_name=config.SERVER_LOGGER_NAME,
        log_mode="rotate",
        log_name=f"{config.SERVER_LOGGER_NAME}.log",
    )

    server = FastApiServer(
        device_cls=Xdm1000Ctrl,
        router_cls=Xdm1000Router,
        config=config,
        api_spec=xdm1000_api_spec,
        device_kwargs={"port": PORT},
        logger=logger,
        log_level="INFO",
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

起動する。

```bash
python server_xdm1000.py
```

起動後、サーバーは次のアドレスで待ち受ける。

```text
http://127.0.0.1:8000
```

## web I/F

`ese774_frame` は OpenAPI により API を提供する。Python 以外の言語から接続する場合は、この Web API を利用できる。

現在 `server_fastapi/spec.py` で公開される XDM1000 API は以下である。

```text
get_state
is_running
idn
set_mode
set_range
set_auto_range
set_integration_speed
set_continue_interval
set_continue_duration
set_continue_count
meas
meas_continue
get_result
wait_until_done
```

すべて `object_name="xdm1000"`、HTTP method は `post` である。

## クライアント単発測定スクリプト

`DeviceProxy` を用いて XDM1000 サーバーに接続し、DC 電圧を 1 回測定する。

現在の API では `meas_one_shot("voltage_dc")` は使用しない。測定前に `set_mode()` で測定モードを設定し、必要に応じて `set_auto_range()`、`set_integration_speed()` を設定してから `meas()` を呼ぶ。

```python
#!/usr/bin/env python3
"""XDM1000 電圧単発測定サンプルである。"""

from __future__ import annotations

from ese774_frame import DeviceProxy


def main() -> None:
    """DeviceProxy 経由で XDM1000 の DC 電圧を 1 回測定する。"""
    dmm = DeviceProxy("Xdm1000Ctrl", config="xdm1000.yml", async_mode=False)

    dmm.set_mode("voltage_dc")
    dmm.set_auto_range(True)
    dmm.set_integration_speed("F")

    result = dmm.meas()
    print(result)


if __name__ == "__main__":
    main()
```

## クライアント連続測定スクリプト

連続測定では、測定モードと連続測定条件を事前に設定する。

```python
#!/usr/bin/env python3
"""XDM1000 電圧連続測定サンプルである。"""

from __future__ import annotations

from ese774_frame import DeviceProxy


def main() -> None:
    """DeviceProxy 経由で XDM1000 の DC 電圧を連続測定する。"""
    dmm = DeviceProxy("Xdm1000Ctrl", config="xdm1000.yml", async_mode=False)

    dmm.set_mode("voltage_dc")
    dmm.set_auto_range(True)
    dmm.set_integration_speed("F")

    dmm.set_continue_interval(0.1)
    dmm.set_continue_duration(10.0)

    job = dmm.meas_continue()
    print(job)

    dmm.wait_until_done()

    result = dmm.get_result()
    print(result)


if __name__ == "__main__":
    main()
```

`meas_continue()` の前に `set_continue_duration()` または `set_continue_count()` の少なくとも一方を設定する必要がある。両方が None の場合は `ValueError` である。

## クライアント側で回数指定する例

測定時間ではなく測定回数で終了させる場合は `set_continue_count()` を使う。

```python
#!/usr/bin/env python3
"""XDM1000 回数指定連続測定サンプルである。"""

from __future__ import annotations

from ese774_frame import DeviceProxy


def main() -> None:
    """100 回の DC 電圧測定を行う。"""
    dmm = DeviceProxy("Xdm1000Ctrl", config="xdm1000.yml", async_mode=False)

    dmm.set_mode("voltage_dc")
    dmm.set_auto_range(True)
    dmm.set_integration_speed("F")

    dmm.set_continue_interval(0.1)
    dmm.set_continue_count(100)

    dmm.meas_continue()
    dmm.wait_until_done()

    result = dmm.get_result(clear=True)
    print(result)


if __name__ == "__main__":
    main()
```

## ローカル利用

FastAPI サーバーを使わず、Python から直接 `Xdm1000Ctrl` を使うこともできる。

```python
#!/usr/bin/env python3
"""XDM1000 ローカル単発測定サンプルである。"""

from __future__ import annotations

from xdm1000.xdm1000_ctrl import Xdm1000Ctrl


def main() -> None:
    """ローカルプロセスで XDM1000 を直接制御する。"""
    dmm = Xdm1000Ctrl(port="/dev/cu.usbserial-10", use_process=True)

    try:
        dmm.set_mode("voltage_dc")
        dmm.set_auto_range(True)
        dmm.set_integration_speed("F")
        print(dmm.meas())
    finally:
        dmm.close()


if __name__ == "__main__":
    main()
```

`use_process=True` では worker process が SCPI 通信を担当する。`use_process=False` では同一プロセス内で SCPI オブジェクトを直接持つ。

## Windows サービスでのサーバースクリプト起動

Windows では Python によるサーバー起動をサービスとして運用できる。サービス化には NSSM などの外部ツールを用いる。

サービスは通常のログインユーザー環境ではなく、サービスとして設定されたユーザー権限で動作する。System 権限で動作させる場合、通常ユーザーの環境変数、Python 環境、シリアルポートアクセス権、設定ファイル配置とは異なる点に注意する。

初期導入時やトラブル対応時は、まず通常の Python プロセスとして起動し、通信と API が正常に動作することを確認するのがよい。

## Linux デーモンでのサーバースクリプト起動

Linux では systemd により Python サーバーをバックグラウンド起動できる。

古い環境では init.d 系の起動方式が使われている場合がある。SPring-8 などの古いシステムでは、systemd か init.d かの違いを確認してからサービス化する必要がある。

## 旧チュートリアルからの置換

旧 API を使った例は現在のプログラムと齟齬がある。

旧コード

```python
print(dmm.meas_one_shot("voltage_dc"))
```

現在の API

```python
dmm.set_mode("voltage_dc")
print(dmm.meas())
```

旧コード

```python
dmm.start_continuous_meas("voltage_dc", duration=10.0, interval=0.1)
result = dmm.get_continuous_result()
```

現在の API

```python
dmm.set_mode("voltage_dc")
dmm.set_continue_interval(0.1)
dmm.set_continue_duration(10.0)
dmm.meas_continue()
dmm.wait_until_done()
result = dmm.get_result()
```
