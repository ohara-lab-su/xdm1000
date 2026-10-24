[![en](https://img.shields.io/badge/lang-en-red.svg)](https://ohara-lab-su.github.io/xdm1000/en/manual/fastapi_layer.html) [![ja](https://img.shields.io/badge/lang-ja-blue.svg)](https://ohara-lab-su.github.io/xdm1000/ja/manual/fastapi_layer.html)

> **API generation warning:** The endpoint names listed on this page come from the supplied FastAPI-layer document. The [control API reference](ctrl_api_reference.md), however, identifies `set_mode()`, `meas_continue()`, and `get_result()` as the current control API and treats `start_continuous_meas()` and related names as legacy methods. **Do not assume these legacy names are currently available as FastAPI endpoints.** Check `server_fastapi/spec.py` in the actual installed version. The current implementation cannot be verified from the supplied documents alone.


# FastAPI Exposure Layer

The FastAPI adapter exposes selected `Xdm1000Ctrl` methods through `ese774_frame`. API specifications are declared in `server_fastapi/spec.py`; request/response models live in `models/common.py`, routing in `routers/xdm1000_router.py`, and synchronous/asynchronous clients in `clients/`. Raw SCPI operations are not published. **Compatibility note:** this source describes an earlier API set; consult the current control-layer reference before using method names.

> **Documentation scope:** This English guide is an abridged technical companion to the complete Japanese manual. This page is a summary of the supplied Japanese document; consult the Japanese version for details and complete examples.

## Layout

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

## API specification

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

## Request and response models

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

## Router

## Clients

## Excluded APIs

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
