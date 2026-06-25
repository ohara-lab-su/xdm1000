#!/usr/bin/env python3
"""idn(), get_state(), is_running() を確認する。"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, show


def main():
    dmm = make_dmm()

    show("idn", dmm.idn())
    show("get_state before setup", dmm.get_state())
    show("is_running before measurement", dmm.is_running())

    show("set_mode", dmm.set_mode("voltage_dc"))
    show("set_auto_range", dmm.set_auto_range(True))
    show("set_integration_speed", dmm.set_integration_speed("F"))
    show("get_state after setup", dmm.get_state())


if __name__ == "__main__":
    main()
