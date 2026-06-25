#!/usr/bin/env python3
"""XDM1000 FastAPI サーバー起動例である。"""

from __future__ import annotations

import logging
from types import SimpleNamespace

from ese774_frame import FastApiServer

from xdm1000.xdm1000_ctrl import Xdm1000Ctrl
from xdm1000.server_fastapi.spec import xdm1000_api_spec
from xdm1000.server_fastapi.routers.xdm1000_router import Xdm1000Router

from x_logger import XLogger

# PORT = "/dev/cu.usbserial-140"
# PORT = "/dev/cu.usbserial-10"
PORT = "com8"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000


def main() -> None:
    """XDM1000 をサーバー側デバイスクラスとして起動する。"""
    # logging.basicConfig(level=logging.INFO)
    # logger = logging.getLogger("xdm1000.server")

    config = SimpleNamespace(
        PORT=PORT,
        SERVER_HOST=SERVER_HOST,
        SERVER_PORT=SERVER_PORT,
        SERVER_LOGGER_NAME="xdm1000.server",
    )

    logger = XLogger(
        log_level="debug",
        logger_name=config.SERVER_LOGGER_NAME,
        log_mode="rotate",
        # log_mode="file",
        log_name=f"{config.SERVER_LOGGER_NAME}.log",
    )

    server = FastApiServer(
        device_cls=Xdm1000Ctrl,
        router_cls=Xdm1000Router,
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
