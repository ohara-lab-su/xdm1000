#!/usr/bin/env python3
"""XDM1000 server_fastapi 用 .pyi 生成スクリプトである。"""

from __future__ import annotations

from pathlib import Path

from ese774_frame.routers.make_pyi_device_router import make_pyi_device_router
from ese774_frame.clients.make_pyi_device_client import make_pyi_device_client

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


if __name__ == "__main__":
    main()
