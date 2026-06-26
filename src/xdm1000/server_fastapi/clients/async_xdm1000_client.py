#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
K.NAKADA, kengo.nakada@gmail.com
XDM1000 用 async client
"""

import asyncio

from xdm1000.server_fastapi.spec import xdm1000_api_spec
from ese774_frame.clients.async_device_client import AsyncDeviceClient


class AsyncXdm1000Client(AsyncDeviceClient):
    """XDM1000 API spec を設定した AsyncDeviceClient である。"""

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
        timeout_sec=60.0,
    ):
        """XDM1000 用 async client を初期化する。

        Args:
            config: 設定オブジェクト。SERVER_HOST を正式名として読む。
            server_host: 接続先ホスト名または IP アドレス。
            server_ip: 旧名の接続先指定。server_host 未指定時だけ使う。
            server_port: 接続先ポート番号。
            base_url: 明示的に指定する base URL。
            api_spec: ese774_frame の API spec。
            logger: ロガー。
            log_level: ログレベル。
            object_name: ese774_frame の object 名。
            timeout_sec: HTTP タイムアウト秒。
        """
        resolved_host = None
        resolved_port = None

        if config is not None:
            try:
                resolved_host = config.SERVER_IP
            except AttributeError:
                pass
            try:
                resolved_host = config.SERVER_HOST
            except AttributeError:
                pass
            try:
                resolved_port = config.SERVER_PORT
            except AttributeError:
                pass

        if server_ip is not None:
            resolved_host = server_ip
        if server_host is not None:
            resolved_host = server_host
        if server_port is not None:
            resolved_port = server_port

        if resolved_host is None:
            resolved_host = "127.0.0.1"
        if resolved_port is None:
            resolved_port = 8000

        if api_spec is None:
            api_spec = xdm1000_api_spec

        AsyncDeviceClient.__init__(
            self,
            server_ip=resolved_host,
            server_port=resolved_port,
            base_url=base_url,
            api_spec=api_spec,
            logger=logger,
            log_level=log_level,
            object_name=object_name,
            timeout_sec=timeout_sec,
        )

    async def wait_until_done(self, poll_interval=0.2):
        """クライアント側で running が False になるまで待つ。"""
        while await self.is_running():
            await asyncio.sleep(poll_interval)

        return await self.get_state()
