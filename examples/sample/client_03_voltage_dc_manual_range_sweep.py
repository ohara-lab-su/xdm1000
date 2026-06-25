#!/usr/bin/env python3
"""DC 電圧の手動レンジを切り替えながら 1 回ずつ測定する。

SCPI manual の CONFigure:VOLTage:DC のレンジ指定例に合わせる。
実信号が各レンジを超えないことを確認してから実行する。
"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, configure_single, measure_single, show

VOLTAGE_DC_RANGES = [0.5, 5, 50, 500, 1000]


def main():
    dmm = make_dmm()
    for range_value in VOLTAGE_DC_RANGES:
        show("manual DC voltage range", range_value)
        configure_single(
            dmm,
            mode="voltage_dc",
            range_value=range_value,
            auto_range=False,
            speed="F",
        )
        measure_single(dmm, "voltage_dc")


if __name__ == "__main__":
    main()
