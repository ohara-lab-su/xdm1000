#!/usr/bin/env python3
"""meas_continue(wait=...) が連続測定開始前待機として動作することを確認する。"""

from __future__ import annotations

import time

from xdm1000_client_test_common import make_dmm, configure_single, wait_job_and_get_result, show


def main():
    dmm = make_dmm()
    configure_single(dmm, mode="voltage_dc", auto_range=True, speed="F")
    show("set_continue_interval", dmm.set_continue_interval(0.1))
    show("set_continue_duration(None)", dmm.set_continue_duration(None))
    show("set_continue_count", dmm.set_continue_count(3))

    wait = 0.5
    t0 = time.perf_counter()
    show("meas_continue(wait=0.5)", dmm.meas_continue(wait=wait))
    elapsed = time.perf_counter() - t0
    show("elapsed until job accepted", elapsed)

    if elapsed < wait:
        raise AssertionError("wait 指定より短い時間で job が開始されている。")

    wait_job_and_get_result(dmm)


if __name__ == "__main__":
    main()
