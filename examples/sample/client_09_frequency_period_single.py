#!/usr/bin/env python3
"""周波数と周期を 1 回ずつ測定する。

周波数/周期は現在の ctrl API では set_range() を使わず、mode と integration_speed を設定して測定する。
入力信号が XDM1000 の周波数測定範囲内であることを確認してから実行する。
"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, show, measure_single


def measure_mode(mode):
    dmm = make_dmm()
    show("set_mode", dmm.set_mode(mode))
    show("set_integration_speed", dmm.set_integration_speed("S"))
    measure_single(dmm, mode)


def main():
    measure_mode("frequency")
    measure_mode("period")


if __name__ == "__main__":
    main()
