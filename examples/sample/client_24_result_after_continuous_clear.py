#!/usr/bin/env python3
"""連続測定後の get_result(clear=True) を確認する。"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, configure_single, wait_job_and_get_result, show


def main():
    dmm = make_dmm()
    configure_single(dmm, mode="voltage_dc", auto_range=True, speed="F")
    show("set_continue_interval", dmm.set_continue_interval(0.1))
    show("set_continue_duration(None)", dmm.set_continue_duration(None))
    show("set_continue_count", dmm.set_continue_count(3))

    show("meas_continue", dmm.meas_continue())
    wait_job_and_get_result(dmm)

    show("get_result(clear=True)", dmm.get_result(clear=True))
    cleared = dmm.get_result()
    show("get_result after clear", cleared)
    if cleared is not None:
        raise AssertionError("clear=True 後に continuous result が残っている。")


if __name__ == "__main__":
    main()
