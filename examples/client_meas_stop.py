#!/usr/bin/env python3
"""stop() テスト"""

from ese774_frame import DeviceProxy


def main():
    dmm = DeviceProxy(
        "Xdm1000Ctrl",
        config="xdm1000.yml",
        async_mode=False,
    )

    print(dmm.stop())


if __name__ == "__main__":
    main()
