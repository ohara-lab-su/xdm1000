#!/usr/bin/env python3
"""XDM1000 電圧測定サンプル"""

from xdm1000.server_fastapi.clients.sync_xdm1000_client import SyncXdm1000Client

HOST = "127.0.0.1"
PORT = 8000


def main():

    dmm = SyncXdm1000Client(HOST, PORT)

    print(dmm.measure_one_shot("voltage_dc"))


if __name__ == "__main__":
    main()
