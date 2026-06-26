#!/usr/bin/env python3
"""XDM1000 continuous 測定中の途中結果を表で表示するサンプルである。"""

import time
from ese774_frame import DeviceProxy
import xdm1000.server_fastapi  # noqa: F401

POLL_INTERVAL_SEC = 0.5
MAX_PRINT_SAMPLES = 10


def print_header() -> None:
    """表示表のヘッダーを出力する。"""
    print("running count last_index last_value t_rel_end read_elapsed")


def print_no_result(running: bool) -> None:
    """結果がまだ存在しない場合の表示を行う。"""
    print("{0} 0 - - - -".format(running))


def print_result_row(running: bool, result: dict) -> None:
    """get_result() の結果から途中経過を 1 行で表示する。"""
    samples = result["samples"]
    count = len(samples)

    if count == 0:
        print("{0} 0 - - - -".format(running))
        return

    last_sample = samples[-1]

    print(
        "{0} {1} {2} {3} {4} {5}".format(
            running,
            count,
            last_sample["index"],
            last_sample["value"],
            last_sample["t_rel_end"],
            last_sample["read_elapsed"],
        )
    )


def print_recent_samples(result: dict) -> None:
    """直近の samples を表示する。"""
    samples = result["samples"]

    if len(samples) <= MAX_PRINT_SAMPLES:
        selected_samples = samples
    else:
        selected_samples = samples[-MAX_PRINT_SAMPLES:]

    print("")
    print("recent samples")
    print("index value t_rel_start t_rel_end read_elapsed")

    for sample in selected_samples:
        print(
            "{0} {1} {2} {3} {4}".format(
                sample["index"],
                sample["value"],
                sample["t_rel_start"],
                sample["t_rel_end"],
                sample["read_elapsed"],
            )
        )


def main() -> None:
    """continuous 測定中の途中結果を get_result() で取得して表示する。"""
    dmm = DeviceProxy(
        "Xdm1000Ctrl",
        config="xdm1000.yml",
        async_mode=False,
    )

    print_header()

    while True:
        running = dmm.is_running()
        result = dmm.get_result()

        if result is None:
            print_no_result(running)
        else:
            print_result_row(running, result)

        if not running:
            break

        time.sleep(POLL_INTERVAL_SEC)

    final_result = dmm.get_result()

    if final_result is not None:
        print_recent_samples(final_result)


if __name__ == "__main__":
    main()
