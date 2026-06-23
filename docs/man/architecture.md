# システム構成

OWON XDM1000/XDM1241 用の `ese774_frame` 透過サーバー構成である。

## 構成

```text
project_root/
├── src/
│   └── xdm1000/
│       ├── xdm1000_scpi.py
│       ├── xdm1000_ctrl.py
│       └── server_fastapi/
│           ├── spec.py
│           ├── make.py
│           ├── models/
│           ├── routers/
│           └── clients/
└── examples/
    ├── serve_xdm1000.py
    └── meas_xdm1000.py
```

`xdm1000_ctrl.py` はローカル制御クラスであり、ローカル利用では直接使う。
サーバー利用では同じ制御クラスを `FastApiServer` の `device_cls`
として渡し、`server_fastapi/spec.py` で公開 API を選別する。

## .pyi 生成

```bash
python -m xdm1000.server_fastapi.make
```

## サーバー起動

```bash
python examples/serve_xdm1000.py
```

## 測定サンプル

```bash
python examples/meas_xdm1000.py
```
