#!/usr/bin/env python3
"""XDM1000 用 sync client である。"""

from __future__ import annotations

from typing import Any, Optional

from ese774_frame.clients.sync_device_client import SyncDeviceClient

from xdm1000.server_fastapi.spec import xdm1000_api_spec


class SyncXDM1000Client(SyncDeviceClient):
    """XDM1000 API spec を設定した SyncDeviceClient である。"""

    def __init__(
        self,
        server_ip: str = "127.0.0.1",
        server_port: int = 8000,
        base_url: Optional[str] = None,
        api_spec: Optional[list] = None,
        logger: Optional[Any] = None,
        log_level: str = "INFO",
        object_name: str = "xdm1000",
    ):
        super().__init__(
            server_ip=server_ip,
            server_port=server_port,
            base_url=base_url,
            api_spec=api_spec or xdm1000_api_spec,
            logger=logger,
            log_level=log_level,
            object_name=object_name,
        )
