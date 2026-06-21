#!/usr/bin/env python3
"""XDM1000 FastAPI 用 Pydantic model 群である。"""

from __future__ import annotations

from typing import Optional, Tuple, Union

from pydantic import BaseModel

ScpiValue = Union[str, int, float]


class RawCommandRequest(BaseModel):
    """応答を要求しない SCPI コマンドを表す。"""

    command: str


class ScpiQueryRequest(BaseModel):
    """応答を要求する SCPI クエリを表す。"""

    command: str


class BoolRequest(BaseModel):
    """bool 値 1 個を受け取る。"""

    enabled: bool


class DisplayRequest(BaseModel):
    """XDM1000 の display 番号を受け取る。"""

    display: int = 1


class FunctionRequest(BaseModel):
    """測定 function と display 番号を受け取る。"""

    function: str
    display: int = 1


class RtdTypeRequest(BaseModel):
    """RTD type を受け取る。"""

    rtd_type: str


class TemperatureUnitRequest(BaseModel):
    """温度単位を受け取る。"""

    unit: str


class TemperatureShowRequest(BaseModel):
    """温度表示 mode を受け取る。"""

    mode: str


class OptionalRtdTypeRequest(BaseModel):
    """省略可能な RTD type を受け取る。"""

    rtd_type: Optional[str] = None


class OptionalSelectorRequest(BaseModel):
    """省略可能な selector を受け取る。"""

    selector: Optional[str] = None


class RangeRequest(BaseModel):
    """レンジ値を受け取る。"""

    range_value: ScpiValue = "AUTO"


class ContinuityThresholdRequest(BaseModel):
    """導通しきい値を受け取る。"""

    value: ScpiValue


class ResistanceOhmRequest(BaseModel):
    """抵抗値 [ohm] を受け取る。"""

    resistance_ohm: ScpiValue


class CalcFunctionRequest(BaseModel):
    """CALCulate:FUNCtion の function を受け取る。"""

    function: str


class NullOffsetRequest(BaseModel):
    """NULL offset 値を受け取る。"""

    value: ScpiValue


class RangeIndexRequest(BaseModel):
    """RANGE の index または DEF を受け取る。"""

    range_index: Union[int, str]


class RateRequest(BaseModel):
    """RATE の speed を受け取る。"""

    speed: str


class StringResponse(BaseModel):
    """文字列 response である。"""

    value: str


class FloatResponse(BaseModel):
    """float response である。"""

    value: float


class IntResponse(BaseModel):
    """int response である。"""

    value: int


class BoolResponse(BaseModel):
    """bool response である。"""

    value: bool


class MeasureResponse(BaseModel):
    """MEAS? response である。"""

    value: Union[float, Tuple[float, float]]


class AverageStatsResponse(BaseModel):
    """CALCulate:AVERage:ALL? response である。"""

    minimum: float
    maximum: float
    average: float
    count: int
