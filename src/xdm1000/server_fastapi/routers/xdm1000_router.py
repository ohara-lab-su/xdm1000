#!/usr/bin/env python3
"""XDM1000 用 FastAPI router である。"""

from __future__ import annotations

from typing import Any, Optional

from ese774_frame.routers.device_router import DeviceRouter


class Xdm1000Router(DeviceRouter):
    """XDM1000 制御クラスを ese774_frame で透過公開する router である。"""

    def __init__(
        self,
        device_instance: Any,
        api_spec=None,
        logger: Optional[Any] = None,
        log_level: str = "INFO",
    ):
        super().__init__(
            device_instance=device_instance,
            api_spec=api_spec,
            logger=logger,
            log_level=log_level,
        )
