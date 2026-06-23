# システム構成

本構成は、OWON XDM1000/XDM1241 系デジタルマルチメータを Python から制御するための構成である。低レベル SCPI 層、測定器として扱う上位制御層、長時間測定用 worker、FastAPI/ese774_frame 公開層を分離する。

## ファイル構成

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

## レイヤ構成

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

## ローカル利用

ローカル利用では `Xdm1000Ctrl` を直接生成する。

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

## SCPI 直接利用

低レベル確認では `Xdm1000Scpi` を直接使う。

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

## FastAPI 利用

FastAPI 利用では、`Xdm1000Ctrl` をサーバー側のデバイス実体として生成し、`server_fastapi/spec.py` の `xdm1000_api_spec` に定義された API だけを公開する。`xdm1000_ctrl.py` は FastAPI に依存しない。

## 設定

`config.py` は `Config` クラスを提供する。YAML を渡した場合は YAML の値がインスタンス属性として設定される。SCPI/ctrl の通信パラメータでは config がコンストラクタ引数より優先される。

主な設定値は次である。

```yaml
PORT: "/dev/cu.usbserial-10"
BAUDRATE: 115200
TIMEOUT: 2.0
LOGGER_LEVEL: "debug"
SERVER_HOST: "127.0.0.1"
SERVER_PORT: 8000
```
