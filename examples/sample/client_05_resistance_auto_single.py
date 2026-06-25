#!/usr/bin/env python3
"""抵抗を AUTO レンジで 1 回測定する。"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, configure_single, measure_single


def main():
    dmm = make_dmm()
    configure_single(dmm, mode="resistance", auto_range=True, speed="S")
    measure_single(dmm, "resistance")


if __name__ == "__main__":
    main()
