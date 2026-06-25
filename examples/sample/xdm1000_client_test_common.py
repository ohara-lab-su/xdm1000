#!/usr/bin/env python3
"""XDM1000 ctrl sync test 共通関数である。"""

from __future__ import annotations

import pprint
import time

from ese774_frame import DeviceProxy

# DeviceProxy 登録を実行するために import する。
import xdm1000.server_fastapi  # noqa: F401


def make_dmm():
    """sync DeviceProxy を生成する。"""
    return DeviceProxy(
        "Xdm1000Ctrl",
        config="xdm1000.yml",
        async_mode=False,
    )


def show(title, value):
    """見出し付きで値を表示する。"""
    print("")
    print("== {0} ==".format(title))
    pprint.pprint(value, width=120)


def require_single_result(result, expected_mode):
    """単発測定結果の基本形を検査する。"""
    if not isinstance(result, dict):
        raise AssertionError("result が dict ではない。")
    if result.get("type") != "single":
        raise AssertionError("type が single ではない: {0!r}".format(result.get("type")))
    if result.get("mode") != expected_mode:
        raise AssertionError("mode が一致しない: {0!r}".format(result.get("mode")))
    if "value" not in result:
        raise AssertionError("value が存在しない。")


def require_continuous_result(result, expected_mode):
    """連続測定結果の基本形を検査する。"""
    if not isinstance(result, dict):
        raise AssertionError("result が dict ではない。")
    if result.get("type") != "continuous":
        raise AssertionError("type が continuous ではない: {0!r}".format(result.get("type")))
    if result.get("mode") != expected_mode:
        raise AssertionError("mode が一致しない: {0!r}".format(result.get("mode")))
    if "samples" not in result:
        raise AssertionError("samples が存在しない。")


def configure_single(dmm, mode, range_value=None, auto_range=True, speed="F"):
    """単発測定に必要な設定を行う。"""
    show("set_mode", dmm.set_mode(mode))
    if auto_range:
        show("set_auto_range(True)", dmm.set_auto_range(True))
    else:
        show("set_range({0!r})".format(range_value), dmm.set_range(range_value))
    show("set_integration_speed({0!r})".format(speed), dmm.set_integration_speed(speed))


def measure_single(dmm, mode, wait=None):
    """単発測定を実行し、結果の基本形を検査する。"""
    result = dmm.meas(wait=wait)
    show("meas", result)
    require_single_result(result, mode)
    show("get_result", dmm.get_result())
    return result


def run_voltage_dc_single(range_value=None, auto_range=True, speed="F"):
    """DC 電圧の単発測定を行う。"""
    dmm = make_dmm()
    configure_single(
        dmm=dmm,
        mode="voltage_dc",
        range_value=range_value,
        auto_range=auto_range,
        speed=speed,
    )
    return measure_single(dmm, "voltage_dc")


def wait_job_and_get_result(dmm, poll_interval=0.05):
    """連続測定の完了を待ち、結果を取得する。"""
    show("is_running before wait", dmm.is_running())
    state = dmm.wait_until_done(poll_interval=poll_interval)
    show("wait_until_done", state)
    show("is_running after wait", dmm.is_running())
    result = dmm.get_result()
    show("get_result", result)
    return result


def sleep_briefly():
    """running 状態確認用に短時間待つ。"""
    time.sleep(0.1)
