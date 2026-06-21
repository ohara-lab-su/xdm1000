#!/usr/bin/env python3
"""XDM1000 FastAPI 用 Pydantic model 群である。"""

from __future__ import annotations

from typing import Any, Dict, Optional, Union

from pydantic import BaseModel

ScpiValue = Union[str, int, float]


class EmptyResponse(BaseModel):
    """空 response である。"""

    pass


class StringResponse(BaseModel):
    """文字列 response である。"""

    value: str


class BoolResponse(BaseModel):
    """bool response である。"""

    value: bool


class DictResponse(BaseModel):
    """dict response である。"""

    value: Dict[str, Any]


class OptionalDictResponse(BaseModel):
    """Optional[dict] response である。"""

    value: Optional[Dict[str, Any]] = None


class MeasModeRequest(BaseModel):
    """測定種別・レンジ・速度を受け取る。"""

    kind: str
    range_value: ScpiValue = "AUTO"
    rate: str = "F"


class MeasOneShotRequest(BaseModel):
    """1 shot 測定条件を受け取る。"""

    kind: str
    range_value: ScpiValue = "AUTO"
    rate: str = "F"
    settle: float = 0.0


class MeasRequest(BaseModel):
    """短縮 1 shot 測定条件を受け取る。"""

    kind: str = "voltage_dc"
    range_value: ScpiValue = "AUTO"
    rate: str = "F"
    settle: float = 0.0


class MeasSimpleRequest(BaseModel):
    """電圧・電流 1 shot 測定条件を受け取る。"""

    range_value: ScpiValue = "AUTO"
    rate: str = "F"


class ContinuousMeasRequest(BaseModel):
    """擬似 continuous 測定条件を受け取る。"""

    kind: str
    duration: float
    range_value: ScpiValue = "AUTO"
    rate: str = "F"
    interval: float = 0.0
    settle: float = 0.0


class StatisticsModeRequest(BaseModel):
    """statistics mode 測定条件を受け取る。"""

    kind: str
    duration: float
    range_value: ScpiValue = "AUTO"
    rate: str = "F"
    settle: float = 0.0


class ClearRequest(BaseModel):
    """取得後に保存結果を clear するかどうかを受け取る。"""

    clear: bool = False


class WaitUntilDoneRequest(BaseModel):
    """running 終了待ちの poll interval を受け取る。"""

    poll_interval: float = 0.2
