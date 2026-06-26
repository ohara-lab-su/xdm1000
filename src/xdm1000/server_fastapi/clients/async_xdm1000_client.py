#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""XDM1000 用 async client である。"""

import asyncio

from xdm1000.server_fastapi.spec import xdm1000_api_spec
from ese774_frame.clients.async_device_client import AsyncDeviceClient


class AsyncXdm1000Client(AsyncDeviceClient):
    """XDM1000 API spec を設定した AsyncDeviceClient である。"""

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
        timeout_sec=60.0,
    ):
        """
        XDM1000 用 async client を初期化する。

        config があれば SERVER_IP または SERVER_HOST / SERVER_PORT を優先し、
        無ければ引数を使う。
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

        AsyncDeviceClient.__init__(
            self,
            server_ip=server_ip,
            server_port=server_port,
            base_url=base_url,
            api_spec=api_spec,
            logger=logger,
            log_level=log_level,
            object_name=object_name,
            timeout_sec=timeout_sec,
        )

    async def wait_until_done(self, poll_interval=0.2):
        """クライアント側で running が False になるまで待つ。

        サーバー側の wait_until_done API は呼ばない。
        サーバーを長時間ブロックしないため、is_running() を周期的に呼ぶ。
        """
        while await self.is_running():
            await asyncio.sleep(poll_interval)

        return await self.get_state()

    async def wait_until_done(self, poll_interval=0.2):
        """クライアント側で running が False になるまで待つ。"""
        while await self.is_running():
            await asyncio.sleep(poll_interval)

        return await self.get_state()
