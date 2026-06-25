# xdm1000/config.py

"""
Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""

import os
import yaml
from typing import Any, Dict, Optional, Union
from pathlib import Path
import inspect


class Config:
    # --- xdm1000-server
    SERVER_IP = "127.0.0.1"  # server
    SERVER_PORT = 8000
    CLIENT_LOGGER_NAME = "xdm1000_client"
    SERVER_LOGGER_NAME = "xdm1000_server"

    # --- xdm1000 device
    PORT = "/dev/cu.usbserial-10"  # XDM1000 serial port
    BAUDRATE = 115200
    TIMEOUT = 2.0

    # --- server param
    LOGGER_LEVEL = "debug"

    def __init__(self, yaml_path=None):
        # インスタンスで使いたいときだけ、ここで個別設定
        if yaml_path:
            self._load_yaml(yaml_path=yaml_path, depth=3)

    @classmethod
    def load_yaml(
        cls,
        yaml_path,
    ):
        """クラスとして使う"""
        # if yaml_path is None:
        #     yaml_path = os.environ.get("XDM1000_CONFIG_YAML")
        #     if yaml_path is None:
        #         return

        # 新しいパス解決ロジックを使用
        resolved_path = cls._resolve_path(yaml_path=yaml_path, depth=2)
        with open(resolved_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        for k, v in data.items():
            if hasattr(cls, k):
                setattr(cls, k, v)
            else:
                print("NO SUCH VAR:", k)

    def _load_yaml(
        self,
        *,
        yaml_path,
        depth: int,
    ):
        """コンストラクタから呼び出す"""
        # インスタンス用：インスタンスdictにのみ上書き
        print("load_yaml:", yaml_path)
        if yaml_path is None:
            yaml_path = os.environ.get("XDM1000_CONFIG_YAML")
            if yaml_path is None:
                return

        # 新しいパス解決ロジックを使用 (引数で受け取った depth を渡す)
        resolved_path = self._resolve_path(yaml_path=yaml_path, depth=depth)

        print("resolved_path:", resolved_path)
        with open(resolved_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for k, v in data.items():
            setattr(self, k, v)

    @staticmethod
    def _resolve_path(
        *,
        yaml_path: Union[str, Path],
        depth: int,
    ) -> Path:
        """
        絶対パスならそのまま、相対パスならこのメソッドの呼び出し元を基準に解決する
        """
        path = Path(yaml_path)

        # 1. 絶対パス判定（/ や C:\ など）
        if path.is_absolute():
            return path

        # 2. 実行ファイルの場所を特定
        caller_frame = inspect.stack()[depth]
        caller_file = Path(caller_frame.filename).resolve()

        # 3. 実行ファイルのディレクトリ + 相対パス を結合
        return (caller_file.parent / path).resolve()
