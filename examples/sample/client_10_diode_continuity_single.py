#!/usr/bin/env python3
"""ダイオード測定と導通測定を 1 回ずつ行う。

これらは現在の ctrl API では set_range() を使わず、mode を設定して測定する。
"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, show, measure_single


def measure_mode(mode):
    dmm = make_dmm()
    show("set_mode", dmm.set_mode(mode))
    show("set_integration_speed", dmm.set_integration_speed("S"))
    measure_single(dmm, mode)


def main():
    measure_mode("diode")
    measure_mode("continuity")


if __name__ == "__main__":
    main()
