#!/usr/bin/env python3
"""DC 電圧を AUTO レンジで 1 回測定する。"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, configure_single, measure_single


def main():
    dmm = make_dmm()
    configure_single(dmm, mode="voltage_dc", auto_range=True, speed="F")
    measure_single(dmm, "voltage_dc")


if __name__ == "__main__":
    main()
