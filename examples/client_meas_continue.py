#!/usr/bin/env python3
"""
K.NAKADA, kengo.nakada@gmail.com
XDM1000 連続測定サンプル。
"""

import logging

from ese774_frame import DeviceProxy

# DeviceProxy 登録を実行するために import する。
import xdm1000.server_fastapi  # noqa: F401
from xdm1000 import Config

# httpx のログを WARNING レベル以上にする（INFO を抑制）
logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> None:
    """サーバー上の XDM1000 から DC 電圧を連続測定する。"""
    # config = Config("xdm1000.yml")
    config = Config("xdm1000_server1.yml")

    dmm = DeviceProxy(
        "Xdm1000Ctrl",
        config=config,
        async_mode=False,
    )

    dmm.set_mode("voltage_dc")
    dmm.set_auto_range(True)
    dmm.set_integration_speed("F")
    dmm.set_continue_interval(0.1)
    #####
    dmm.set_continue_count(100000)
    #####

    print(dmm.meas_continue())
    print(dmm.wait_until_done())
    print(dmm.get_result())


if __name__ == "__main__":
    main()
