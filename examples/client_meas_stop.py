#!/usr/bin/env python3
"""
K.NAKADA, kengo.nakada@gmail.com
測定停止を要求する最小サンプル
"""
import logging

from ese774_frame import DeviceProxy
import xdm1000.server_fastapi  # noqa: F401

# httpx のログを WARNING レベル以上にする（INFO を抑制）
logging.getLogger("httpx").setLevel(logging.WARNING)

dmm = DeviceProxy(
    "Xdm1000Ctrl",
    config="xdm1000.yml",
    async_mode=False,
)

print(dmm.stop())
