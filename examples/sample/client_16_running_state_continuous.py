#!/usr/bin/env python3
"""meas_continue() 開始後の is_running() と get_state() を確認する。"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, configure_single, wait_job_and_get_result, show, sleep_briefly


def main():
    dmm = make_dmm()
    configure_single(dmm, mode="voltage_dc", auto_range=True, speed="F")
    show("set_continue_interval", dmm.set_continue_interval(0.2))
    show("set_continue_duration", dmm.set_continue_duration(1.5))
    show("set_continue_count(None)", dmm.set_continue_count(None))

    show("meas_continue", dmm.meas_continue())
    sleep_briefly()
    show("is_running during measurement", dmm.is_running())
    show("get_state during measurement", dmm.get_state())

    result = wait_job_and_get_result(dmm)
    if result.get("type") != "continuous":
        raise AssertionError("continuous result ではない。")


if __name__ == "__main__":
    main()
