#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from ese774_frame import DeviceProxy
import xdm1000.server_fastapi

dmm = DeviceProxy(
    "Xdm1000Ctrl",
    config="xdm1000.yml",
    async_mode=False,
)

while dmm.is_running():
    print(dmm.get_result())
    time.sleep(0.5)

print(dmm.get_result())
