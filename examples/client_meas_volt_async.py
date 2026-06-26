#!/usr/bin/env python3
"""
K.NAKADA, kengo.nakada@gmail.com
XDM1000 電圧測定 async サンプル
"""

from __future__ import annotations

import asyncio

from ese774_frame import DeviceProxy

# DeviceProxy 登録を実行するために import する。
import xdm1000.server_fastapi  # noqa: F401


async def main() -> None:
    """サーバー上の XDM1000 から async client で DC 電圧を 1 回測定する。"""
    dmm = DeviceProxy(
        "Xdm1000Ctrl",
        config="xdm1000.yml",
        async_mode=True,
    )

    await dmm.set_mode("voltage_dc")
    await dmm.set_auto_range(True)
    await dmm.set_integration_speed("F")

    result = await dmm.meas()
    print(result)
    print(await dmm.get_result())


if __name__ == "__main__":
    asyncio.run(main())
