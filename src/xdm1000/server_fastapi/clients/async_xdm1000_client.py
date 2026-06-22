#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""XDM1000 用 async client である。"""

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

        ese774_frame は透過型であるため、ctrl と同様に config を受けられるようにする。
        config があれば SERVER_IP / SERVER_PORT を優先し、無ければ引数を使う。
        """
        if config is not None:
            server_ip = getattr(config, "SERVER_IP", server_ip)
            server_port = getattr(config, "SERVER_PORT", server_port)

        if server_ip is None:
            server_ip = "127.0.0.1"
        if server_port is None:
            server_port = 8000

        AsyncDeviceClient.__init__(
            self,
            server_ip=server_ip,
            server_port=server_port,
            base_url=base_url,
            api_spec=api_spec or xdm1000_api_spec,
            logger=logger,
            log_level=log_level,
            object_name=object_name,
            timeout_sec=timeout_sec,
        )
