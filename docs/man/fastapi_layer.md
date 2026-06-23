# FastAPI 公開レイヤ

`server_fastapi/` は、`Xdm1000Ctrl` を ese774_frame の透過 API として公開するためのレイヤである。`xdm1000_ctrl.py` 自体は FastAPI に依存しない。

## 構成

```text
server_fastapi/
├── spec.py
├── models/
│   └── common.py
├── routers/
│   └── xdm1000_router.py
└── clients/
    ├── sync_xdm1000_client.py
    └── async_xdm1000_client.py
```

## spec.py

`spec.py` は `xdm1000_api_spec` を定義する。各要素は `ese774_frame.models.api_spec.ApiSpec` であり、`object_name="xdm1000"`、`method="post"` として公開される。

公開 API は次である。

```text
get_state
is_running
stop_job
get_continuous_result
get_statistics_result
idn
set_meas_mode
meas_one_shot
meas
meas_voltage_dc
meas_current_dc
start_continuous_meas
start_statistics_mode
wait_until_done
```

## models/common.py

FastAPI 経由の request/response model を定義する。

主な request model は次である。

```text
MeasModeRequest(kind, range_value="AUTO", rate="F")
MeasOneShotRequest(kind, range_value="AUTO", rate="F", settle=0.0)
MeasRequest(kind="voltage_dc", range_value="AUTO", rate="F", settle=0.0)
MeasSimpleRequest(range_value="AUTO", rate="F")
ContinuousMeasRequest(kind, duration, range_value="AUTO", rate="F", interval=0.0, settle=0.0)
StatisticsModeRequest(kind, duration, range_value="AUTO", rate="F", settle=0.0)
ClearRequest(clear=False)
WaitUntilDoneRequest(poll_interval=0.2)
```

response model として `StringResponse`、`BoolResponse`、`DictResponse`、`OptionalDictResponse` も定義されている。ただし現状の `xdm1000_api_spec` では、`idn` は `StringResponse`、`is_running` は `BoolResponse` を指定し、多くの dict 返却 API は `response_model=None` としている。

## routers/xdm1000_router.py

`Xdm1000Router` は `ese774_frame.routers.device_router.DeviceRouter` の薄い派生クラスである。`device_instance`、`api_spec`、`logger`、`log_level` を親クラスへ渡す。

## clients

`SyncXdm1000Client` と `AsyncXdm1000Client` は、それぞれ ese774_frame の `SyncDeviceClient` / `AsyncDeviceClient` に `xdm1000_api_spec` と `object_name="xdm1000"` を設定する。

両 client は `config`、`server_ip`、`server_port`、`base_url` を受けられる。現状の client 実装は config から `SERVER_IP` と `SERVER_PORT` を参照する。

## 公開しない API

次は FastAPI 公開対象ではない。

```text
remote
local
write
query
query_float
query_int
raw SCPI 操作
_reset_scpi_internal
```
