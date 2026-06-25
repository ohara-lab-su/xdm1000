#!/usr/bin/env python3
"""set_mode() が range_value と auto_range のキャッシュを無効化することを確認する。"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, show


def main():
    dmm = make_dmm()

    show("set_mode voltage_dc", dmm.set_mode("voltage_dc"))
    show("set_range 5", dmm.set_range(5))
    show("state after range", dmm.get_state())

    show("set_mode resistance", dmm.set_mode("resistance"))
    state = dmm.get_state()
    show("state after mode switch", state)

    if state.get("range_value") is not None:
        raise AssertionError("mode 切替後に range_value が残っている。")
    if state.get("auto_range") is not None:
        raise AssertionError("mode 切替後に auto_range が残っている。")


if __name__ == "__main__":
    main()
