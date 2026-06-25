#!/usr/bin/env python3
"""容量レンジを切り替えながら 1 回ずつ測定する。"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, configure_single, measure_single, show

CAPACITANCE_RANGES = [50e-9, 500e-9, 5e-6, 50e-6, 500e-6, 5e-3, 50e-3]


def main():
    dmm = make_dmm()
    for range_value in CAPACITANCE_RANGES:
        show("manual capacitance range", range_value)
        configure_single(
            dmm,
            mode="capacitance",
            range_value=range_value,
            auto_range=False,
            speed="S",
        )
        measure_single(dmm, "capacitance")


if __name__ == "__main__":
    main()
