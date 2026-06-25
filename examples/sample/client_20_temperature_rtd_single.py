#!/usr/bin/env python3
"""RTD 温度測定を 1 回行う。

現在の ctrl API では RTD 種別を指定する API はない。
測定器側の既定または直前設定に従う。
"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, show, measure_single


def main():
    dmm = make_dmm()
    show("set_mode", dmm.set_mode("temperature_rtd"))
    show("set_integration_speed", dmm.set_integration_speed("S"))
    measure_single(dmm, "temperature_rtd")


if __name__ == "__main__":
    main()
