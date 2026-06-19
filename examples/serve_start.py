#!/usr/bin/env python3
"""XDM1000 FastAPI サーバー起動例である。"""

from __future__ import annotations

import logging
from types import SimpleNamespace

try:
    from ese774_frame.servers.api_server import FastApiServer
except ImportError:
    from ese774_frame.api_server import FastApiServer

from xdm1000.xdm1000_ctrl import XDM1241
from xdm1000.server_fastapi.spec import xdm1000_api_spec
from xdm1000.server_fastapi.routers.xdm1000_router import XDM1000Router

PORT = "/dev/cu.usbserial-140"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000


def main() -> None:
    """XDM1000 をサーバー側デバイスクラスとして起動する。"""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("xdm1000.server")

    config = SimpleNamespace(
        PORT=PORT,
        SERVER_HOST=SERVER_HOST,
        SERVER_PORT=SERVER_PORT,
    )

    server = FastApiServer(
        device_cls=XDM1241,
        router_cls=XDM1000Router,
        config=config,
        api_spec=xdm1000_api_spec,
        device_kwargs={"port": PORT},
        logger=logger,
        log_level="INFO",
        lifespan_msg_prefix="XDM1000",
    )
    server.run(
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
