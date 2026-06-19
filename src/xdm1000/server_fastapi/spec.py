#!/usr/bin/env python3
"""XDM1000 FastAPI 透過 API spec である。"""

from __future__ import annotations

from ese774_frame.models.api_spec import ApiSpec

from xdm1000.server_fastapi.models.common import (
    AverageStatsResponse,
    BoolRequest,
    BoolResponse,
    DisplayRequest,
    FloatResponse,
    FunctionRequest,
    IntResponse,
    MeasureResponse,
    CalcFunctionRequest,
    ContinuityThresholdRequest,
    NullOffsetRequest,
    OptionalRtdTypeRequest,
    OptionalSelectorRequest,
    RangeIndexRequest,
    RangeRequest,
    RateRequest,
    RawCommandRequest,
    ResistanceOhmRequest,
    RtdTypeRequest,
    ScpiQueryRequest,
    TemperatureShowRequest,
    TemperatureUnitRequest,
    StringResponse,
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
    # raw SCPI
    _api("write", RawCommandRequest, None, summary="Send raw SCPI command"),
    _api("query", ScpiQueryRequest, StringResponse, summary="Send raw SCPI query"),
    _api(
        "query_float",
        ScpiQueryRequest,
        FloatResponse,
        summary="Send raw SCPI query and parse float",
    ),
    _api(
        "query_int",
        ScpiQueryRequest,
        IntResponse,
        summary="Send raw SCPI query and parse int",
    ),
    # common / system
    _api("idn", None, StringResponse, summary="*IDN?"),
    _api("reset", None, None, summary="*RST"),
    _api("remote", None, None, summary="Enter remote mode"),
    _api("local", None, None, summary="Return to local mode"),
    _api("set_beeper", BoolRequest, None, summary="Set beeper state"),
    _api("get_beeper", None, BoolResponse, summary="Get beeper state"),
    # sense
    _api("set_function", FunctionRequest, None, summary="Set measurement function"),
    _api(
        "get_function",
        DisplayRequest,
        StringResponse,
        summary="Get measurement function",
    ),
    _api("set_temperature_rtd_type", RtdTypeRequest, None, summary="Set RTD type"),
    _api("get_temperature_rtd_type", None, StringResponse, summary="Get RTD type"),
    _api(
        "set_temperature_unit",
        TemperatureUnitRequest,
        None,
        summary="Set temperature unit",
    ),
    _api("get_temperature_unit", None, StringResponse, summary="Get temperature unit"),
    _api(
        "set_temperature_show",
        TemperatureShowRequest,
        None,
        summary="Set temperature display mode",
    ),
    _api(
        "get_temperature_show",
        None,
        StringResponse,
        summary="Get temperature display mode",
    ),
    _api(
        "set_continuity_threshold",
        ContinuityThresholdRequest,
        None,
        summary="Set continuity threshold",
    ),
    # configure
    _api("configure_voltage_dc", RangeRequest, None, summary="Configure DC voltage"),
    _api("configure_voltage_ac", RangeRequest, None, summary="Configure AC voltage"),
    _api("configure_current_dc", RangeRequest, None, summary="Configure DC current"),
    _api("configure_current_ac", RangeRequest, None, summary="Configure AC current"),
    _api(
        "configure_resistance",
        RangeRequest,
        None,
        summary="Configure 2-wire resistance",
    ),
    _api(
        "configure_fresistance",
        RangeRequest,
        None,
        summary="Configure 4-wire resistance",
    ),
    _api("configure_frequency", None, None, summary="Configure frequency"),
    _api("configure_period", None, None, summary="Configure period"),
    _api("configure_capacitance", RangeRequest, None, summary="Configure capacitance"),
    _api(
        "configure_temperature_rtd",
        OptionalRtdTypeRequest,
        None,
        summary="Configure RTD temperature",
    ),
    _api("configure_diode", None, None, summary="Configure diode"),
    _api("configure_continuity", None, None, summary="Configure continuity"),
    # calculate
    _api(
        "get_average_all",
        None,
        AverageStatsResponse,
        summary="Get min/max/average/count",
    ),
    _api("get_average", None, FloatResponse, summary="Get average"),
    _api("get_average_maximum", None, FloatResponse, summary="Get average maximum"),
    _api("get_average_minimum", None, FloatResponse, summary="Get average minimum"),
    _api("set_db_reference", ResistanceOhmRequest, None, summary="Set dB reference"),
    _api("get_db_reference", None, FloatResponse, summary="Get dB reference"),
    _api("set_dbm_reference", ResistanceOhmRequest, None, summary="Set dBm reference"),
    _api("get_dbm_reference", None, FloatResponse, summary="Get dBm reference"),
    _api(
        "set_calc_function",
        CalcFunctionRequest,
        None,
        summary="Set calculation function",
    ),
    _api("get_calc_function", None, StringResponse, summary="Get calculation function"),
    _api("set_null_offset", NullOffsetRequest, None, summary="Set NULL offset"),
    _api(
        "get_null_offset",
        OptionalSelectorRequest,
        FloatResponse,
        summary="Get NULL offset",
    ),
    _api("calc_off", None, None, summary="Disable calculation"),
    # misc / measure
    _api("auto", None, None, summary="Enable autoscale"),
    _api("get_auto", None, BoolResponse, summary="Get autoscale state"),
    _api("set_range", RangeIndexRequest, None, summary="Set current function range"),
    _api("set_rate", RateRequest, None, summary="Set measurement rate"),
    _api("get_rate", None, StringResponse, summary="Get measurement rate"),
    _api("measure_raw", None, StringResponse, summary="MEAS? raw"),
    _api("measure", None, MeasureResponse, summary="MEAS? parsed"),
    _api("measure_main", None, FloatResponse, summary="MEAS1?"),
    _api("measure_sub", None, FloatResponse, summary="MEAS2?"),
]
