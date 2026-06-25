#!/usr/bin/env python3
"""set_continue_count() による連続測定を確認する。"""

from __future__ import annotations

from xdm1000_client_test_common import (
    make_dmm,
    configure_single,
    wait_job_and_get_result,
    require_continuous_result,
    show,
)


def main():
    dmm = make_dmm()
    configure_single(dmm, mode="voltage_dc", auto_range=True, speed="F")

    show("set_continue_interval", dmm.set_continue_interval(0.1))
    show("set_continue_duration(None)", dmm.set_continue_duration(None))
    show("set_continue_count", dmm.set_continue_count(10))

    show("meas_continue", dmm.meas_continue())
    result = wait_job_and_get_result(dmm)
    require_continuous_result(result, "voltage_dc")
    if result.get("stats", {}).get("count") != 10:
        raise AssertionError("測定回数が 10 ではない。")


if __name__ == "__main__":
    main()
