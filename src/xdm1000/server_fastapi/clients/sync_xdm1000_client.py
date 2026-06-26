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
        server_host=None,
        server_ip=None,
        server_port=None,
        base_url=None,
        api_spec=None,
        logger=None,
        log_level="INFO",
        object_name="xdm1000",
    ):
        """XDM1000 用 sync client を初期化する。

        Args:
            config: Config オブジェクト。
            server_host: 接続先ホスト。
            server_ip: 接続先ホストの旧名。
            server_port: 接続先ポート。
            base_url: 接続先 URL。
            api_spec: API 定義。
            logger: ロガー。
            log_level: ログレベル。
            object_name: ese774_frame 上の object 名。

        Raises:
            ValueError: 接続先ホストまたはポートを解決できない場合。
        """
        if server_host is None:
            if server_ip is not None:
                server_host = server_ip

        if config is not None:
            if server_host is None:
                try:
                    server_host = config.SERVER_HOST
                except AttributeError:
                    try:
                        server_host = config.SERVER_IP
                    except AttributeError:
                        pass

            if server_port is None:
                try:
                    server_port = config.SERVER_PORT
                except AttributeError:
                    pass

        if server_host is None:
            raise ValueError("server_host が必要です。")
        if server_port is None:
            raise ValueError("server_port が必要です。")

        if api_spec is None:
            api_spec = xdm1000_api_spec

        SyncDeviceClient.__init__(
            self,
            server_ip=server_host,
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
