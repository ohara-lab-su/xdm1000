#!/usr/bin/env python3
"""meas(wait=...) が測定直前待機として動作することを確認する。"""

from __future__ import annotations

import time

from xdm1000_client_test_common import make_dmm, configure_single, show, require_single_result


def main():
    dmm = make_dmm()
    configure_single(dmm, mode="voltage_dc", auto_range=True, speed="F")

    wait = 0.5
    t0 = time.perf_counter()
    result = dmm.meas(wait=wait)
    elapsed = time.perf_counter() - t0

    show("meas(wait=0.5)", result)
    show("elapsed", elapsed)
    require_single_result(result, "voltage_dc")

    if elapsed < wait:
        raise AssertionError("wait 指定より短い時間で戻っている。")


if __name__ == "__main__":
    main()
