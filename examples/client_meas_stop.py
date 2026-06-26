#!/usr/bin/env python3
"""
K.NAKADA, kengo.nakada@gmail.com
測定停止を要求する最小サンプル
"""

import logging

from ese774_frame import DeviceProxy
from xdm1000 import Config
import xdm1000.server_fastapi  # noqa: F401

# httpx のログを WARNING レベル以上にする（INFO を抑制）
logging.getLogger("httpx").setLevel(logging.WARNING)

# config = Config("xdm1000.yml")
config = Config("xdm1000_server1.yml")

dmm = DeviceProxy(
    "Xdm1000Ctrl",
    config=config,
    async_mode=False,
)

print(dmm.stop())
