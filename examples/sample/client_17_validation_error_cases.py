#!/usr/bin/env python3
"""不正パラメータが例外になることを確認する。

このサンプルは装置を危険な状態にしないソフトウェア検証である。
"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, show


def expect_error(title, func):
    try:
        func()
    except Exception as exc:
        show(title, repr(exc))
        return
    raise AssertionError("{0} が例外にならなかった。".format(title))


def main():
    dmm = make_dmm()

    expect_error("invalid mode", lambda: dmm.set_mode("bad_mode"))
    expect_error("invalid integration speed", lambda: dmm.set_integration_speed("X"))
    expect_error("negative continue interval", lambda: dmm.set_continue_interval(-0.1))
    expect_error("zero continue duration", lambda: dmm.set_continue_duration(0.0))
    expect_error("zero continue count", lambda: dmm.set_continue_count(0))

    # mode 未設定で meas_continue 条件だけを設定しても、meas_continue() は失敗する。
    show("set_continue_count", dmm.set_continue_count(1))
    expect_error("meas_continue without mode", lambda: dmm.meas_continue())


if __name__ == "__main__":
    main()
