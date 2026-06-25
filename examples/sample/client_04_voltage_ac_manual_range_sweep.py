#!/usr/bin/env python3
"""AC 電圧の手動レンジを切り替えながら 1 回ずつ測定する。

SCPI manual の CONFigure:VOLTage:AC のレンジ指定例に合わせる。
AC 電圧入力が安全範囲内であることを確認してから実行する。
"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, configure_single, measure_single, show

VOLTAGE_AC_RANGES = [0.5, 5, 50, 500, 750]


def main():
    dmm = make_dmm()
    for range_value in VOLTAGE_AC_RANGES:
        show("manual AC voltage range", range_value)
        configure_single(
            dmm,
            mode="voltage_ac",
            range_value=range_value,
            auto_range=False,
            speed="S",
        )
        measure_single(dmm, "voltage_ac")


if __name__ == "__main__":
    main()
