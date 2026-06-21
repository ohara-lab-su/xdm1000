#!/usr/bin/env python3
"""XDM1000 FastAPI 透過 API spec である。"""

from __future__ import annotations

from ese774_frame.models.api_spec import ApiSpec

from xdm1000.server_fastapi.models.common import (
    BoolResponse,
    ClearRequest,
    ContinuousMeasRequest,
    MeasModeRequest,
    MeasOneShotRequest,
    MeasRequest,
    MeasSimpleRequest,
    StatisticsModeRequest,
    StringResponse,
    WaitUntilDoneRequest,
)


xdm1000_api_spec = [
    ######################################
    # 状態取得 API
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
        summary="長時間測定中かどうかを取得する",
    ),
    ApiSpec(
        name="stop_job",
        object_name="xdm1000",
        request_model=None,
        response_model=None,
        method="post",
        description="stop_job()",
        summary="実行中の長時間測定に停止要求を出す",
    ),
    ApiSpec(
        name="get_continuous_result",
        object_name="xdm1000",
        request_model=ClearRequest,
        response_model=None,
        method="post",
        description="get_continuous_result(clear=False)",
        summary="連続測定結果を取得する",
    ),
    ApiSpec(
        name="get_statistics_result",
        object_name="xdm1000",
        request_model=ClearRequest,
        response_model=None,
        method="post",
        description="get_statistics_result(clear=False)",
        summary="statistics mode 結果を取得する",
    ),
    ######################################
    # 通常 API
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
        name="set_meas_mode",
        object_name="xdm1000",
        request_model=MeasModeRequest,
        response_model=None,
        method="post",
        description="set_meas_mode(kind, range_value='AUTO', rate='F')",
        summary="測定種別・レンジ・速度を設定する",
    ),
    ApiSpec(
        name="meas_one_shot",
        object_name="xdm1000",
        request_model=MeasOneShotRequest,
        response_model=None,
        method="post",
        description="meas_one_shot(kind, range_value='AUTO', rate='F', settle=0.0)",
        summary="1 shot 測定を実行する",
    ),
    ApiSpec(
        name="meas",
        object_name="xdm1000",
        request_model=MeasRequest,
        response_model=None,
        method="post",
        description="meas(kind='voltage_dc', range_value='AUTO', rate='F', settle=0.0)",
        summary="1 shot 測定の短縮 API",
    ),
    ApiSpec(
        name="meas_voltage_dc",
        object_name="xdm1000",
        request_model=MeasSimpleRequest,
        response_model=None,
        method="post",
        description="meas_voltage_dc(range_value='AUTO', rate='F')",
        summary="DC 電圧を 1 shot 測定する",
    ),
    ApiSpec(
        name="meas_current_dc",
        object_name="xdm1000",
        request_model=MeasSimpleRequest,
        response_model=None,
        method="post",
        description="meas_current_dc(range_value='AUTO', rate='F')",
        summary="DC 電流を 1 shot 測定する",
    ),
    ######################################
    # 長時間測定 API
    ApiSpec(
        name="start_continuous_meas",
        object_name="xdm1000",
        request_model=ContinuousMeasRequest,
        response_model=None,
        method="post",
        description="start_continuous_meas(kind, duration, range_value='AUTO', rate='F', interval=0.0, settle=0.0)",
        summary="擬似 continuous 測定を開始する",
    ),
    ApiSpec(
        name="start_statistics_mode",
        object_name="xdm1000",
        request_model=StatisticsModeRequest,
        response_model=None,
        method="post",
        description="start_statistics_mode(kind, duration, range_value='AUTO', rate='F', settle=0.0)",
        summary="statistics mode テスト測定を開始する",
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
