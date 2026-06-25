#!/usr/bin/env python3
"""get_result(clear=True) の保存結果消去を確認する。"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, configure_single, measure_single, show


def main():
    dmm = make_dmm()
    configure_single(dmm, mode="voltage_dc", auto_range=True, speed="F")
    measure_single(dmm, "voltage_dc")

    show("get_result(clear=True)", dmm.get_result(clear=True))
    cleared = dmm.get_result()
    show("get_result after clear", cleared)
    if cleared is not None:
        raise AssertionError("clear=True 後に result が残っている。")


if __name__ == "__main__":
    main()
