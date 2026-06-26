#!/usr/bin/env python3
"""XDM1000 連続測定の途中結果を get_result() で表示するサンプルである。"""

from __future__ import annotations

import time

from ese774_frame import DeviceProxy

import xdm1000.server_fastapi  # noqa: F401


def main() -> None:
    dmm = DeviceProxy(
        "Xdm1000Ctrl",
        config="xdm1000.yml",
        async_mode=False,
    )

    while True:
        result = dmm.get_result()
        print(result)
        if result is not None and not result.get("running", False):
            break
        time.sleep(0.5)


if __name__ == "__main__":
    main()
