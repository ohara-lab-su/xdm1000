#!/usr/bin/env python3
"""
K.NAKADA, kengo.nakada@gmail.com
XDM1000 FastAPI 用 Pydantic model 群
"""

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


class ModeRequest(BaseModel):
    """測定モードを受け取る。"""

    mode: str


class RangeRequest(BaseModel):
    """測定レンジを受け取る。"""

    range_value: ScpiValue


class AutoRangeRequest(BaseModel):
    """オートレンジ設定を受け取る。"""

    enabled: bool


class IntegrationSpeedRequest(BaseModel):
    """内部測定速度を受け取る。"""

    speed: str


class ContinueIntervalRequest(BaseModel):
    """連続測定間隔を受け取る。"""

    interval: float


class ContinueDurationRequest(BaseModel):
    """連続測定時間を受け取る。None で無効化する。"""

    duration: Optional[float] = None


class ContinueCountRequest(BaseModel):
    """連続測定回数を受け取る。None で無効化する。"""

    count: Optional[int] = None


class WaitRequest(BaseModel):
    """測定前待機時間を受け取る。None なら待機しない。"""

    wait: Optional[float] = None


class ClearRequest(BaseModel):
    """取得後に保存結果を clear するかどうかを受け取る。"""

    clear: bool = False


class WaitUntilDoneRequest(BaseModel):
    """running 終了待ちの poll interval を受け取る。"""

    poll_interval: float = 0.2
