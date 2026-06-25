#!/usr/bin/env python3
"""set_continue_duration() による連続測定を確認する。"""

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
    show("set_continue_count(None)", dmm.set_continue_count(None))
    show("set_continue_duration", dmm.set_continue_duration(1.0))

    show("meas_continue", dmm.meas_continue())
    result = wait_job_and_get_result(dmm)
    require_continuous_result(result, "voltage_dc")
    if result.get("stats", {}).get("count", 0) <= 0:
        raise AssertionError("測定点が取得されていない。")


if __name__ == "__main__":
    main()
