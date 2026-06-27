from typing import Any, Literal, Optional, overload

from xdm1000.server_fastapi.spec import xdm1000_api_spec
from xdm1000.server_fastapi.routers import Xdm1000Router
from xdm1000.server_fastapi.clients import SyncXdm1000Client
from xdm1000.server_fastapi.clients import AsyncXdm1000Client

@overload
def DeviceProxy(
    device_class: Literal["Xdm1000Ctrl"],
    *args: Any,
    async_mode: Literal[False] = False,
    **kwargs: Any,
) -> SyncXdm1000Client: ...

@overload
def DeviceProxy(
    device_class: Literal["Xdm1000Ctrl"],
    *args: Any,
    async_mode: Literal[True],
    **kwargs: Any,
) -> AsyncXdm1000Client: ...

@overload
def DeviceProxy(
    device_class: Literal["xdm1000"],
    *args: Any,
    async_mode: Literal[False] = False,
    **kwargs: Any,
) -> SyncXdm1000Client: ...

@overload
def DeviceProxy(
    device_class: Literal["xdm1000"],
    *args: Any,
    async_mode: Literal[True],
    **kwargs: Any,
) -> AsyncXdm1000Client: ...

def DeviceProxy(
    device_class: str,
    *args: Any,
    async_mode: Optional[bool] = None,
    **kwargs: Any,
) -> Any: ...

__all__ = [
    "xdm1000_api_spec",
    "Xdm1000Router",
    "SyncXdm1000Client",
    "AsyncXdm1000Client",
    "DeviceProxy",
]
