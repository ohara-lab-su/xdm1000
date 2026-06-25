#!/usr/bin/env python3
"""integration_speed F/M/S が DC 電圧測定に反映されることを確認する。"""

from __future__ import annotations

from xdm1000_client_test_common import make_dmm, configure_single, measure_single, show

SPEEDS = ["F", "M", "S"]


def main():
    dmm = make_dmm()
    for speed in SPEEDS:
        show("integration_speed", speed)
        configure_single(dmm, mode="voltage_dc", auto_range=True, speed=speed)
        result = measure_single(dmm, "voltage_dc")
        if result.get("integration_speed") != speed:
            raise AssertionError("integration_speed が結果に反映されていない。")


if __name__ == "__main__":
    main()
