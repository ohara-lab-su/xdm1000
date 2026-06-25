#!/usr/bin/env python3
"""2 線式抵抗レンジを切り替えながら 1 回ずつ測定する。"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, configure_single, measure_single, show

RESISTANCE_RANGES = [500, 5e3, 50e3, 500e3, 5e6, 50e6, 500e6]


def main():
    dmm = make_dmm()
    for range_value in RESISTANCE_RANGES:
        show("manual resistance range", range_value)
        configure_single(
            dmm,
            mode="resistance",
            range_value=range_value,
            auto_range=False,
            speed="S",
        )
        measure_single(dmm, "resistance")


if __name__ == "__main__":
    main()
