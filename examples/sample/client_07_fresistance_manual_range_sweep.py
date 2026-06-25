#!/usr/bin/env python3
"""4 線式抵抗レンジを切り替えながら 1 回ずつ測定する。

SCPI manual では 4 線式抵抗の最大レンジは 50 kΩ とされているため、
500 Ω, 5 kΩ, 50 kΩ のみを確認する。
"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, configure_single, measure_single, show

FRESISTANCE_RANGES = [500, 5e3, 50e3]


def main():
    dmm = make_dmm()
    for range_value in FRESISTANCE_RANGES:
        show("manual four-wire resistance range", range_value)
        configure_single(
            dmm,
            mode="fresistance",
            range_value=range_value,
            auto_range=False,
            speed="S",
        )
        measure_single(dmm, "fresistance")


if __name__ == "__main__":
    main()
