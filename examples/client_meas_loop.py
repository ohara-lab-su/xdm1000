#!/usr/bin/env python3
"""XDM1000 電圧測定サンプル"""

from __future__ import annotations
from ese774_frame import DeviceProxy
import time

# DeviceProxy 登録を実行するために import する。
import xdm1000.server_fastapi  # noqa: F401


def main() -> None:
    """サーバー上の XDM1000 から DC 電圧を 1 回測定する。"""
    dmm = DeviceProxy(
        "Xdm1000Ctrl",
        config="xdm1000.yml",
        async_mode=False,
    )

    dmm.set_mode("voltage_dc")
    dmm.set_auto_range(True)
    dmm.set_integration_speed("F")

    while True:
        result = dmm.meas()
        print(result)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
