#!/usr/bin/env python3
"""XDM1000 server_fastapi 用 .pyi 生成スクリプトである。"""

from __future__ import annotations

from pathlib import Path

from xdm1000.server_fastapi.spec import xdm1000_api_spec


def _import_make_pyi_device_client():
    candidates = [
        "ese774_frame.tools.make_pyi_device_client",
        "ese774_frame.generators.make_pyi_device_client",
        "ese774_frame.make_pyi_device_client",
    ]
    for module_name in candidates:
        try:
            module = __import__(module_name, fromlist=["make_pyi_device_client"])
            return module.make_pyi_device_client
        except Exception:
            pass
    raise ImportError("make_pyi_device_client が ese774_frame から見つからない")


def _import_make_pyi_device_router():
    candidates = [
        "ese774_frame.tools.make_pyi_device_router",
        "ese774_frame.generators.make_pyi_device_router",
        "ese774_frame.make_pyi_device_router",
    ]
    for module_name in candidates:
        try:
            module = __import__(module_name, fromlist=["make_pyi_device_router"])
            return module.make_pyi_device_router
        except Exception:
            pass
    raise ImportError("make_pyi_device_router が ese774_frame から見つからない")


def main() -> None:
    """server_fastapi 配下の client/router .pyi を生成する。"""
    root = Path(__file__).resolve().parent

    make_pyi_device_client = _import_make_pyi_device_client()
    make_pyi_device_router = _import_make_pyi_device_router()

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
