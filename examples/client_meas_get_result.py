#!/usr/bin/env python3
"""XDM1000 連続測定サンプルである。"""

from __future__ import annotations

from ese774_frame import DeviceProxy

# DeviceProxy 登録を実行するために import する。
import xdm1000.server_fastapi  # noqa: F401


def main() -> None:
    """サーバー上の XDM1000 から DC 電圧を連続測定する。"""
    dmm = DeviceProxy(
        "Xdm1000Ctrl",
        config="xdm1000.yml",
        async_mode=False,
    )

    print(dmm.get_result())


if __name__ == "__main__":
    main()
