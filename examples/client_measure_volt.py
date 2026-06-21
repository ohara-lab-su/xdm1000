#!/usr/bin/env python3
"""XDM1000 FastAPI クライアント測定例である。"""

from __future__ import annotations

import time

from xdm1000.server_fastapi.clients.sync_xdm1000_client import SyncXDM1000Client

SERVER_IP = "127.0.0.1"
SERVER_PORT = 8000


def main() -> None:
    """サーバー側の XDM1000 制御クラスを透過 API として操作する。"""
    dmm = SyncXDM1000Client(
        server_ip=SERVER_IP,
        server_port=SERVER_PORT,
    )

    dmm.remote()
    try:
        print("IDN:", dmm.idn())
        dmm.configure_voltage_dc("AUTO")
        dmm.set_rate("M")
        time.sleep(0.5)

        for _ in range(10):
            print(dmm.meas_main())
            time.sleep(0.5)
    finally:
        dmm.local()


if __name__ == "__main__":
    main()
