# xdm1000/server_fastapi/__init__.py

from ese774_frame import DeviceProxy
from ese774_frame.clients import register_device_proxy

from xdm1000.server_fastapi.spec import xdm1000_api_spec
from xdm1000.server_fastapi.routers import Xdm1000Router
from xdm1000.server_fastapi.clients import (
    SyncXdm1000Client,
    AsyncXdm1000Client,
)
from xdm1000.server_fastapi.models import *

register_device_proxy(
    "Xdm1000Ctrl",
    async_client_cls=AsyncXdm1000Client,
    sync_client_cls=SyncXdm1000Client,
    api_spec=xdm1000_api_spec,
    default_async_mode=True,
    aliases=["xdm1000"],
)

__all__ = [
    "xdm1000_api_spec",
    "Xdm1000Router",
    "SyncXdm1000Client",
    "AsyncXdm1000Client",
    "DeviceProxy",
]
