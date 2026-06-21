#!/usr/bin/env python3
"""XDM1000 FastAPI 透過 API spec である。"""

from __future__ import annotations

from ese774_frame.models.api_spec import ApiSpec

from xdm1000.server_fastapi.models.common import (
    BoolResponse,
    ClearRequest,
    ContinuousMeasRequest,
    DictResponse,
    MeasModeRequest,
    MeasOneShotRequest,
    MeasRequest,
    MeasSimpleRequest,
    OptionalDictResponse,
    StatisticsModeRequest,
    StringResponse,
    WaitUntilDoneRequest,
)

OBJECT_NAME = "xdm1000"


def _api(name, request_model, response_model, *, summary="", description=""):
    return ApiSpec(
        name=name,
        object_name=OBJECT_NAME,
        request_model=request_model,
        response_model=response_model,
        method="post",
        summary=summary,
        description=description,
    )


xdm1000_api_spec = [
    # 状態取得 API
    _api("get_state", None, DictResponse, summary="Get current state"),
    _api("is_running", None, BoolResponse, summary="Get running flag"),
    _api("stop_job", None, DictResponse, summary="Request running job stop"),
    _api(
        "get_continuous_result",
        ClearRequest,
        OptionalDictResponse,
        summary="Get continuous measurement result",
    ),
    _api(
        "get_statistics_result",
        ClearRequest,
        OptionalDictResponse,
        summary="Get statistics mode result",
    ),

    # 通常 API
    _api("idn", None, StringResponse, summary="*IDN?"),
    _api(
        "set_meas_mode",
        MeasModeRequest,
        DictResponse,
        summary="Set measurement mode",
    ),
    _api(
        "meas_one_shot",
        MeasOneShotRequest,
        DictResponse,
        summary="Execute one shot measurement",
    ),
    _api(
        "meas",
        MeasRequest,
        DictResponse,
        summary="Execute one shot measurement shortcut",
    ),
    _api(
        "meas_voltage_dc",
        MeasSimpleRequest,
        DictResponse,
        summary="Execute DC voltage one shot measurement",
    ),
    _api(
        "meas_current_dc",
        MeasSimpleRequest,
        DictResponse,
        summary="Execute DC current one shot measurement",
    ),

    # 長時間測定 API
    _api(
        "start_continuous_meas",
        ContinuousMeasRequest,
        DictResponse,
        summary="Start pseudo continuous measurement",
    ),
    _api(
        "start_statistics_mode",
        StatisticsModeRequest,
        DictResponse,
        summary="Start statistics mode test",
    ),
    _api(
        "wait_until_done",
        WaitUntilDoneRequest,
        DictResponse,
        summary="Wait until running job is done",
    ),
]
