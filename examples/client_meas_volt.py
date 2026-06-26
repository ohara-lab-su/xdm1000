#!/usr/bin/env python3
"""
K.NAKADA, kengo.nakada@gmail.com
XDM1000 電圧測定サンプル
"""
import logging

from ese774_frame import DeviceProxy

# DeviceProxy 登録を実行するために import する。
import xdm1000.server_fastapi  # noqa: F401

# httpx のログを WARNING レベル以上にする（INFO を抑制）
logging.getLogger("httpx").setLevel(logging.WARNING)

def main() -> None:
    """サーバー上の XDM1000 から DC 電圧を 1 回測定する。"""
    dmm = DeviceProxy(
        "Xdm1000Ctrl",
        config="xdm1000.yml",
        async_mode=False,
    )

    dmm.set_mode("voltage_dc")
    dmm.set_auto_range(True)
    # dmm.set_range(5.0)
    dmm.set_range("500mV")
    dmm.set_integration_speed("F")

    result = dmm.meas()
    print(result)
    print(dmm.get_result())


if __name__ == "__main__":
    main()
