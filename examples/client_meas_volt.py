# client_meas_volt.py（修正版）

#!/usr/bin/env python3
"""XDM1000 電圧測定サンプル"""

from ese774_frame import DeviceProxy
from xdm1000.server import SyncXdm1000Client

HOST = "127.0.0.1"
PORT = 8000


def main():
    # dmm = SyncXdm1002Client(HOST, PORT)
    # dmm = SyncXdm1002Client(config="xdm1000.yml")
    dmm = DeviceProxy("Xdm1002Ctrl", config="xdm1000.yml", async_mode=False)

    dmm.set_mode("voltage_dc")
    print(dmm.meas())


if __name__ == "__main__":
    main()
