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
        import_lines=[
            "from xdm1000.server_fastapi.spec import xdm1000_api_spec",
            "from xdm1000.server_fastapi.routers import Xdm1000Router",
            "from xdm1000.server_fastapi.clients import SyncXdm1000Client",
            "from xdm1000.server_fastapi.clients import AsyncXdm1000Client",
        ],
        device_class="Xdm1000Ctrl",
        aliases=["xdm1000"],
        sync_client_class_name="SyncXdm1000Client",
        async_client_class_name="AsyncXdm1000Client",
        all_names=[
            "xdm1000_api_spec",
            "Xdm1000Router",
            "SyncXdm1000Client",
            "AsyncXdm1000Client",
            "DeviceProxy",
        ],
    )


if __name__ == "__main__":
    main()
