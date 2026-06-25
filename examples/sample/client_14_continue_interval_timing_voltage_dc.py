#!/usr/bin/env python3
"""set_continue_interval() の時間間隔が結果に反映されることを確認する。"""

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

    interval = 0.2
    count = 5
    show("set_continue_interval", dmm.set_continue_interval(interval))
    show("set_continue_duration(None)", dmm.set_continue_duration(None))
    show("set_continue_count", dmm.set_continue_count(count))

    show("meas_continue", dmm.meas_continue())
    result = wait_job_and_get_result(dmm)
    require_continuous_result(result, "voltage_dc")

    samples = result.get("samples", [])
    if len(samples) != count:
        raise AssertionError("測定点数が期待値と異なる。")

    # 厳密なリアルタイム性は OS と通信に依存するため、ここでは大きな破綻だけ確認する。
    if len(samples) >= 2:
        measured_span = samples[-1]["t_rel_start"] - samples[0]["t_rel_start"]
        expected_min = interval * (count - 1) * 0.7
        show("measured span", measured_span)
        if measured_span < expected_min:
            raise AssertionError("interval が短すぎる可能性がある。")


if __name__ == "__main__":
    main()
