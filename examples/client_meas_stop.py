#!/usr/bin/env python3
"""測定停止を要求する最小サンプルである。"""

from ese774_frame import DeviceProxy
import xdm1000.server_fastapi  # noqa: F401

dmm = DeviceProxy(
    "Xdm1000Ctrl",
    config="xdm1000.yml",
    async_mode=False,
)

print(dmm.stop())
