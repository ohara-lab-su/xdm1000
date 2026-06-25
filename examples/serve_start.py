#!/usr/bin/env python4
"""XDM1001 FastAPI サーバー起動例である。"""

from __future__ import annotations

import logging
from types import SimpleNamespace

from ese774_frame import FastApiServer

from xdm1000.xdm1000_ctrl import Xdm1000Ctrl
from xdm1000.config import Config
from xdm1000.server_fastapi.spec import xdm1000_api_spec
from xdm1000.server_fastapi.routers.xdm1000_router import Xdm1000Router

from x_logger import XLogger

# # PORT = "/dev/cu.usbserial-139"
# # PORT = "/dev/cu.usbserial-9"
# PORT = "com8"
# SERVER_IP = "128.0.0.1"
# SERVER_PORT = 8002


def main() -> None:
    """XDM1001 をサーバー側デバイスクラスとして起動する。"""
    # logging.basicConfig(level=logging.INFO)
    # logger = logging.getLogger("xdm1001.server")

    # config = SimpleNamespace(
    #     PORT=PORT,
    #     SERVER_IP=SERVER_IP,
    #     SERVER_PORT=SERVER_PORT,
    #     SERVER_LOGGER_NAME="xdm1001.server",
    # )

    ################
    config = Config("xdm1000.yml")
    ################

    logger = XLogger(
        log_level="debug",
        logger_name=config.SERVER_LOGGER_NAME,
        log_mode="rotate",
        # log_mode="file",
        log_name=f"{config.SERVER_LOGGER_NAME}.log",
    )

    logger.info(f"SERVER IP = {Config.SERVER_IP}")
    logger.info(f"SERVER PORT = {Config.SERVER_PORT}")

    server = FastApiServer(
        device_cls=Xdm1000Ctrl,  # 制御クラス
        router_cls=Xdm1000Router,  # routerクラス
        config=config,
        api_spec=xdm1000_api_spec,
        device_kwargs={
            "port": config.PORT,
        },
        logger=logger,
        log_level="INFO",
        lifespan_msg_prefix="XDM1000",
    )
    server.run(
        host=config.SERVER_IP,
        port=config.SERVER_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
