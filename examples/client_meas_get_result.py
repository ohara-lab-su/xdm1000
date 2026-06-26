#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
K.NAKADA, kengo.nakada@gmail.com
"""

import time
import logging

from ese774_frame import DeviceProxy
from xdm1000 import Config
import xdm1000.server_fastapi

# httpx のログを WARNING レベル以上にする（INFO を抑制）
logging.getLogger("httpx").setLevel(logging.WARNING)

# config = Config("xdm1000.yml")
config = Config("xdm1000_server1.yml")

dmm = DeviceProxy(
    "Xdm1000Ctrl",
    config=config,
    async_mode=False,
)

while dmm.is_running():
    print(dmm.get_result())
    time.sleep(0.5)

print(dmm.get_result())
