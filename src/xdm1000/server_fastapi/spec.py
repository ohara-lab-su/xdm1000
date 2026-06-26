#!/usr/bin/env python3
"""
XDM1000 FastAPI 透過 API spec
K.NAKADA, kengo.nakada@gmail.com
"""

from typing import Optional, Union
from pydantic import BaseModel
from ese774_frame.models.api_spec import ApiSpec
from xdm1000.server_fastapi.models.common import (
    AutoRangeRequest,
    BoolResponse,
    ClearRequest,
    ContinueCountRequest,
    ContinueDurationRequest,
    ContinueIntervalRequest,
    IntegrationSpeedRequest,
    ModeRequest,
    StringResponse,
    WaitRequest,
    WaitUntilDoneRequest,
)


class RangeRequest(BaseModel):
    """set_range() 用の要求モデルである。"""

    value: Optional[Union[str, int, float]] = None
    index: Optional[int] = None
    range_value: Optional[Union[str, int, float]] = None


xdm1000_api_spec = [
    ApiSpec(
        name="get_state",
        object_name="xdm1000",
        request_model=None,
        response_model=None,
        method="post",
        description="get_state()",
        summary="現在の状態を取得する",
    ),
    ApiSpec(
        name="is_running",
        object_name="xdm1000",
        request_model=None,
        response_model=BoolResponse,
        method="post",
        description="is_running()",
        summary="連続測定中かどうかを取得する",
    ),
    ApiSpec(
        name="idn",
        object_name="xdm1000",
        request_model=None,
        response_model=StringResponse,
        method="post",
        description="idn()",
        summary="*IDN? を取得する",
    ),
    ApiSpec(
        name="set_mode",
        object_name="xdm1000",
        request_model=ModeRequest,
        response_model=None,
        method="post",
        description="set_mode(mode)",
        summary="測定モードを設定する",
    ),
    ApiSpec(
        name="set_range",
        object_name="xdm1000",
        request_model=RangeRequest,
        response_model=None,
        method="post",
        description="set_range(value=None, index=None, range_value=None)",
        summary="測定レンジを物理量または離散番号で設定する",
    ),
    ApiSpec(
        name="set_auto_range",
        object_name="xdm1000",
        request_model=AutoRangeRequest,
        response_model=None,
        method="post",
        description="set_auto_range(enabled)",
        summary="オートレンジを設定する",
    ),
    ApiSpec(
        name="set_integration_speed",
        object_name="xdm1000",
        request_model=IntegrationSpeedRequest,
        response_model=None,
        method="post",
        description="set_integration_speed(speed)",
        summary="内部測定速度を設定する",
    ),
    ApiSpec(
        name="set_continue_interval",
        object_name="xdm1000",
        request_model=ContinueIntervalRequest,
        response_model=None,
        method="post",
        description="set_continue_interval(interval)",
        summary="連続測定の測定間隔を設定する",
    ),
    ApiSpec(
        name="set_continue_duration",
        object_name="xdm1000",
        request_model=ContinueDurationRequest,
        response_model=None,
        method="post",
        description="set_continue_duration(duration)",
        summary="連続測定の最大測定時間を設定する",
    ),
    ApiSpec(
        name="set_continue_count",
        object_name="xdm1000",
        request_model=ContinueCountRequest,
        response_model=None,
        method="post",
        description="set_continue_count(count)",
        summary="連続測定の最大測定回数を設定する",
    ),
    ApiSpec(
        name="meas",
        object_name="xdm1000",
        request_model=WaitRequest,
        response_model=None,
        method="post",
        description="meas(wait=None)",
        summary="現在設定で 1 回測定する",
    ),
    ApiSpec(
        name="meas_continue",
        object_name="xdm1000",
        request_model=WaitRequest,
        response_model=None,
        method="post",
        description="meas_continue(wait=None)",
        summary="現在設定で連続測定を開始する",
    ),
    ApiSpec(
        name="get_result",
        object_name="xdm1000",
        request_model=ClearRequest,
        response_model=None,
        method="post",
        description="get_result(clear=False)",
        summary="直近の単発または連続測定結果を取得する",
    ),
    ApiSpec(
        name="stop",
        object_name="xdm1000",
        request_model=None,
        response_model=None,
        method="post",
        description="stop()",
        summary="実行中の測定に停止要求を出す",
    ),
    ApiSpec(
        name="wait_until_done",
        object_name="xdm1000",
        request_model=WaitUntilDoneRequest,
        response_model=None,
        method="post",
        description="wait_until_done(poll_interval=0.2)",
        summary="running が終わるまで待つ",
    ),
]
