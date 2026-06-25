#!/usr/bin/env python3
"""DC 電流レンジを切り替えながら測定するためのガード付きサンプルである。

電流測定は入力端子・結線・ヒューズの扱いを間違えると危険である。
必ず電流入力端子、測定対象、レンジ上限を確認してから
RUN_CURRENT_TESTS = True に変更する。
"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, configure_single, measure_single, show

RUN_CURRENT_TESTS = False

# XDM1000 系の代表的な DC 電流レンジである。
CURRENT_DC_RANGES = [500e-6, 5000e-6, 50e-3, 500e-3, 5, 10]


def main():
    if not RUN_CURRENT_TESTS:
        print("current test is disabled. Set RUN_CURRENT_TESTS = True after checking wiring and fuse.")
        return

    dmm = make_dmm()
    for range_value in CURRENT_DC_RANGES:
        show("manual DC current range", range_value)
        configure_single(
            dmm,
            mode="current_dc",
            range_value=range_value,
            auto_range=False,
            speed="S",
        )
        measure_single(dmm, "current_dc")


if __name__ == "__main__":
    main()
