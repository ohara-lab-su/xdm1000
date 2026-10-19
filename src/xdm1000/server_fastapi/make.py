#!/usr/bin/env python
"""
K.NAKADA, kengo.nakada@gmail.com
XDM1000 server_fastapi 用 .pyi 生成スクリプト
"""

from pathlib import Path

from ese774_frame.routers.make_pyi_device_router import make_pyi_device_router
from ese774_frame.clients.make_pyi_device_client import make_pyi_device_client
from ese774_frame.clients.make_pyi_device_proxy import make_pyi_device_proxy

from xdm1000.server_fastapi.spec import xdm1000_api_spec


def main() -> None:
    """server_fastapi 配下の client/router .pyi を生成する。"""
    root = Path(__file__).resolve().parent

    make_pyi_device_client(
        filename=str(root / "clients" / "async_xdm1000_client.pyi"),
        api_spec=xdm1000_api_spec,
        class_name="AsyncXdm1000Client",
        async_mode=True,
    )

    make_pyi_device_client(
        filename=str(root / "clients" / "sync_xdm1000_client.pyi"),
        api_spec=xdm1000_api_spec,
        class_name="SyncXdm1000Client",
        async_mode=False,
    )

    make_pyi_device_router(
        filename=str(root / "routers" / "xdm1000_router.pyi"),
        api_spec=xdm1000_api_spec,
        class_name="Xdm1000Router",
    )

    make_pyi_device_proxy(
        filename=str(root / "__init__.pyi"),
        device_names=["xdm1000"],
        async_client_module="xdm1000.server_fastapi.clients",
        async_client_class="AsyncXdm1000Client",
        sync_client_module="xdm1000.server_fastapi.clients",
        sync_client_class="SyncXdm1000Client",
        default_async_mode=True,
        proxy_name="DeviceProxy",
        create_proxy_name="create_device_proxy",
    )


if __name__ == "__main__":
    main()
