#!/usr/bin/env python3
"""auto_range=False は直前の手動レンジを必要とすることを確認する。"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, show, measure_single


def expect_error(title, func):
    try:
        func()
    except Exception as exc:
        show(title, repr(exc))
        return
    raise AssertionError("{0} が例外にならなかった。".format(title))


def main():
    dmm = make_dmm()
    show("set_mode", dmm.set_mode("voltage_dc"))
    expect_error("set_auto_range(False) before set_range", lambda: dmm.set_auto_range(False))

    show("set_range", dmm.set_range(5))
    show("set_auto_range(False) after set_range", dmm.set_auto_range(False))
    show("set_integration_speed", dmm.set_integration_speed("F"))
    measure_single(dmm, "voltage_dc")


if __name__ == "__main__":
    main()
