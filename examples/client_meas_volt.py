#!/usr/bin/env python3
"""XDM1000 FastAPI クライアント測定例である。"""

from __future__ import annotations

import time

from xdm1000.server_fastapi.clients.sync_xdm1000_client import SyncXdm1000Client

SERVER_IP = "127.0.0.1"
SERVER_PORT = 8000

RANGE_VALUE = "AUTO"

# RANGE_VALUE = 10
# RANGE_VALUE = 100
# RANGE_VALUE = 1000

RATE = "M"

# RATE = "F"
# RATE = "S"


def main() -> None:
    """サーバー側の XDM1000 制御クラスを透過 API として操作する。"""
    dmm = SyncXdm1000Client(
        server_ip=SERVER_IP,
        server_port=SERVER_PORT,
    )

    print("state:", dmm.get_state())
    print("IDN:", dmm.idn())

    dmm.set_meas_mode(
        kind="voltage_dc",
        range_value=RANGE_VALUE,
        rate=RATE,
    )

    time.sleep(0.5)

    for _ in range(10):
        print(
            dmm.meas_voltage_dc(
                range_value=RANGE_VALUE,
                rate=RATE,
            )
        )
        time.sleep(0.5)


if __name__ == "__main__":
    main()
