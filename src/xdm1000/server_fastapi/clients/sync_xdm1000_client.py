#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
K.NAKADA, kengo.nakada@gmail.com
XDM1000 用 sync client
"""

import time

from xdm1000.server_fastapi.spec import xdm1000_api_spec
from ese774_frame.clients.sync_device_client import SyncDeviceClient


class SyncXdm1000Client(SyncDeviceClient):
    """XDM1000 API spec を設定した SyncDeviceClient である。"""

    def __init__(
        self,
        config=None,
        server_ip=None,
        server_port=None,
        base_url=None,
        api_spec=None,
        logger=None,
        log_level="INFO",
        object_name="xdm1000",
    ):
        """
        XDM1000 用 sync client を初期化する。

        """
        if config is not None:
            try:
                server_ip = config.SERVER_IP
            except AttributeError:
                try:
                    server_ip = config.SERVER_HOST
                except AttributeError:
                    pass

            try:
                server_port = config.SERVER_PORT
            except AttributeError:
                pass

        if server_ip is None:
            server_ip = "127.0.0.1"
        if server_port is None:
            server_port = 8000

        if api_spec is None:
            api_spec = xdm1000_api_spec

        SyncDeviceClient.__init__(
            self,
            server_ip=server_ip,
            server_port=server_port,
            base_url=base_url,
            api_spec=api_spec,
            logger=logger,
            log_level=log_level,
            object_name=object_name,
        )

    def wait_until_done(self, poll_interval=0.2):
        """クライアント側で running が False になるまで待つ。

        サーバー側の wait_until_done API は呼ばない。
        サーバーを長時間ブロックしないため、is_running() を周期的に呼ぶ。
        """
        while self.is_running():
            time.sleep(poll_interval)

        return self.get_state()

    def wait_until_done(self, poll_interval=0.2):
        """クライアント側で running が False になるまで待つ。"""
        while self.is_running():
            time.sleep(poll_interval)

        return self.get_state()

    def wait_until_done(self, poll_interval=0.2):
        """クライアント側で running が False になるまで待つ。"""
        while self.is_running():
            time.sleep(poll_interval)

        return self.get_state()
