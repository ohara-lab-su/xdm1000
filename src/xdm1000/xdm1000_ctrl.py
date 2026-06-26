#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OWON XDM1000 / XDM1241 用の上位制御クラスである。
K.NAKADA, kengo.nakada@gmail.com

このファイルは利用者向けの測定器 API を提供する。SCPI 層は SCPI コマンドの
薄いラッパであり、本ファイルで mode/range/continuous 条件を上位 API として整理する。
"""

from typing import Dict
import math
import multiprocessing as mp
import queue
import time
import uuid

from xdm1000.config import Config
from xdm1000.xdm1000_scpi import Xdm1000Scpi
from xdm1000.xdm1000_worker import _Xdm1000Worker

MODE_TO_SCPI_FUNCTION = {
    "voltage_dc": "VOLT",
    "voltage_ac": "VOLT AC",
    "current_dc": "CURR",
    "current_ac": "CURR AC",
    "resistance": "RES",
    "fresistance": "FRES",
    "frequency": "FREQ",
    "period": "PER",
    "capacitance": "CAP",
    "temperature_rtd": "TEMP",
    "diode": "DIOD",
    "continuity": "CONT",
}


RANGE_SPECS = {
    "voltage_dc": {
        "unit": "V",
        "items": [
            (1, 0.05, "50 mV"),
            (2, 0.5, "500 mV"),
            (3, 5.0, "5 V"),
            (4, 50.0, "50 V"),
            (5, 500.0, "500 V"),
            (6, 1000.0, "1000 V"),
        ],
    },
    "voltage_ac": {
        "unit": "V",
        "items": [
            (1, 0.5, "500 mV"),
            (2, 5.0, "5 V"),
            (3, 50.0, "50 V"),
            (4, 500.0, "500 V"),
            (5, 750.0, "750 V"),
        ],
    },
    "current_dc": {
        "unit": "A",
        "items": [
            (1, 0.0005, "500 uA"),
            (2, 0.005, "5 mA"),
            (3, 0.05, "50 mA"),
            (4, 0.5, "500 mA"),
            (5, 5.0, "5 A"),
            (6, 10.0, "10 A"),
        ],
    },
    "current_ac": {
        "unit": "A",
        "items": [
            (1, 0.0005, "500 uA"),
            (2, 0.005, "5 mA"),
            (3, 0.05, "50 mA"),
            (4, 0.5, "500 mA"),
            (5, 5.0, "5 A"),
            (6, 10.0, "10 A"),
        ],
    },
    "resistance": {
        "unit": "Ohm",
        "items": [
            (1, 500.0, "500 Ohm"),
            (2, 5000.0, "5 kOhm"),
            (3, 50000.0, "50 kOhm"),
            (4, 500000.0, "500 kOhm"),
            (5, 5000000.0, "5 MOhm"),
            (6, 50000000.0, "50 MOhm"),
        ],
    },
    "fresistance": {
        "unit": "Ohm",
        "items": [
            (1, 500.0, "500 Ohm"),
            (2, 5000.0, "5 kOhm"),
            (3, 50000.0, "50 kOhm"),
            (4, 500000.0, "500 kOhm"),
            (5, 5000000.0, "5 MOhm"),
            (6, 50000000.0, "50 MOhm"),
        ],
    },
    "capacitance": {
        "unit": "F",
        "items": [
            (1, 50e-9, "50 nF"),
            (2, 500e-9, "500 nF"),
            (3, 5e-6, "5 uF"),
            (4, 50e-6, "50 uF"),
            (5, 500e-6, "500 uF"),
            (6, 5e-3, "5 mF"),
            (7, 50e-3, "50 mF"),
        ],
    },
    "temperature_rtd": {
        "unit": "sensor",
        "items": [
            (1, "KITS90", "KITS90"),
            (2, "PT100", "PT100"),
        ],
    },
}

_UNIT_FACTORS = {
    "v": ("V", 1.0),
    "mv": ("V", 1.0e-3),
    "a": ("A", 1.0),
    "ma": ("A", 1.0e-3),
    "ua": ("A", 1.0e-6),
    "µa": ("A", 1.0e-6),
    "ohm": ("Ohm", 1.0),
    "ohms": ("Ohm", 1.0),
    "Ω": ("Ohm", 1.0),
    "kohm": ("Ohm", 1.0e3),
    "kω": ("Ohm", 1.0e3),
    "mohm": ("Ohm", 1.0e6),
    "mω": ("Ohm", 1.0e6),
    "f": ("F", 1.0),
    "mf": ("F", 1.0e-3),
    "uf": ("F", 1.0e-6),
    "µf": ("F", 1.0e-6),
    "nf": ("F", 1.0e-9),
}


def _normalize_unit_text(text):
    """単位文字列を内部比較用に正規化する。

    Args:
        text: 正規化対象の単位文字列である。

    Returns:
        空白を除去し、マイクロ記号を統一し、小文字化した文字列である。
    """
    return str(text).strip().replace(" ", "").replace("μ", "µ").lower()


def _float_equal(a, b):
    """レンジ表の離散値比較を行う。

    Args:
        a: 比較対象の数値である。
        b: 比較対象の数値である。

    Returns:
        浮動小数点誤差を許容して一致するとき True を返す。
    """
    return math.isclose(float(a), float(b), rel_tol=1.0e-9, abs_tol=1.0e-15)


def _format_range_choices(mode):
    """エラーメッセージ用に有効レンジ一覧を返す。

    Args:
        mode: ctrl API 上の測定モード名である。

    Returns:
        有効なレンジラベルをカンマ区切りにした文字列である。
        モードがレンジ表にない場合は空文字列を返す。
    """
    spec = RANGE_SPECS.get(mode)
    if spec is None:
        return ""
    return ", ".join([item[2] for item in spec["items"]])


def _parse_range_quantity(mode, range_value):
    """上位 API の物理量レンジ指定を SCPI RANGE 番号へ変換する。

    数値は現在の測定モードの基本単位として扱う。電圧系では V、
    電流系では A、抵抗系では Ohm、静電容量では F である。
    単位付き文字列は "500 mV" と "500mV" の両方を受け付ける。

    Args:
        mode: ctrl API 上の測定モード名である。
        range_value: レンジ指定である。数値、単位付き文字列、または
            temperature_rtd 用センサー名を受け付ける。

    Returns:
        RANGE 番号と表示用レンジラベルの 2 要素 tuple である。

    Raises:
        ValueError: 測定モードが未設定、未対応、またはレンジ指定が
            現在モードの離散レンジに一致しない場合に送出する。
    """
    if mode is None:
        raise ValueError("先に set_mode() で測定モードを設定する必要がある。")
    if mode not in RANGE_SPECS:
        raise ValueError(
            "この測定モードは手動レンジ設定に対応していない: {0!r}".format(mode)
        )

    spec = RANGE_SPECS[mode]
    expected_unit = spec["unit"]

    if expected_unit == "sensor":
        value = str(range_value).strip().upper().replace(" ", "")
        for index, sensor, label in spec["items"]:
            if value == str(sensor).upper():
                return index, label
        raise ValueError(
            "temperature_rtd のレンジは KITS90 または PT100 で指定する: {0!r}".format(
                range_value
            )
        )

    value = range_value
    unit = expected_unit

    if isinstance(range_value, str):
        text = range_value.strip()
        parts = text.split()
        if len(parts) == 1:
            number_text = parts[0]
            unit_text = None
            for suffix in sorted(_UNIT_FACTORS.keys(), key=len, reverse=True):
                if _normalize_unit_text(number_text).endswith(suffix):
                    unit_text = suffix
                    number_text = number_text[: -len(suffix)]
                    break
            if unit_text is None:
                try:
                    value = float(number_text)
                except ValueError:
                    raise ValueError(
                        "レンジ指定を解釈できない: {0!r}".format(range_value)
                    )
            else:
                canonical_unit, factor = _UNIT_FACTORS[_normalize_unit_text(unit_text)]
                if canonical_unit != expected_unit:
                    raise ValueError(
                        "{0} モードでは {1} 単位のレンジを指定する必要がある: {2!r}".format(
                            mode, expected_unit, range_value
                        )
                    )
                value = float(number_text) * factor
                unit = canonical_unit
        elif len(parts) == 2:
            value = float(parts[0])
            unit_key = _normalize_unit_text(parts[1])
            if unit_key not in _UNIT_FACTORS:
                raise ValueError("未対応のレンジ単位である: {0!r}".format(parts[1]))
            canonical_unit, factor = _UNIT_FACTORS[unit_key]
            if canonical_unit != expected_unit:
                raise ValueError(
                    "{0} モードでは {1} 単位のレンジを指定する必要がある: {2!r}".format(
                        mode, expected_unit, range_value
                    )
                )
            value = value * factor
            unit = canonical_unit
        else:
            raise ValueError("レンジ指定を解釈できない: {0!r}".format(range_value))

    if unit != expected_unit:
        raise ValueError(
            "{0} モードでは {1} 単位のレンジを指定する必要がある。".format(
                mode, expected_unit
            )
        )

    value = float(value)
    for index, physical_value, label in spec["items"]:
        if _float_equal(value, physical_value):
            return index, label

    raise ValueError(
        "{0} モードのレンジは離散値のみ指定できる。指定値={1!r}, 有効値={2}".format(
            mode, range_value, _format_range_choices(mode)
        )
    )


def _validate_range_index(mode, range_index):
    """SCPI RANGE 番号を現在モードの範囲で検証する。

    Args:
        mode: ctrl API 上の測定モード名である。
        range_index: 検証対象の RANGE 番号である。

    Returns:
        RANGE 番号と表示用レンジラベルの 2 要素 tuple である。

    Raises:
        ValueError: 測定モードが未設定、未対応、または RANGE 番号が
            現在モードの範囲外である場合に送出する。
    """
    if mode is None:
        raise ValueError("先に set_mode() で測定モードを設定する必要がある。")
    if mode not in RANGE_SPECS:
        raise ValueError(
            "この測定モードは手動レンジ設定に対応していない: {0!r}".format(mode)
        )
    try:
        index = int(range_index)
    except Exception:
        raise ValueError(
            "range_index は整数でなければならない: {0!r}".format(range_index)
        )
    for item_index, physical_value, label in RANGE_SPECS[mode]["items"]:
        if index == item_index:
            return index, label
    raise ValueError(
        "{0} モードの RANGE 番号が範囲外である。指定値={1!r}, 有効値={2}".format(
            mode,
            range_index,
            ", ".join([str(item[0]) for item in RANGE_SPECS[mode]["items"]]),
        )
    )


def _validate_mode(mode):
    """ctrl API の mode 名を SCPI FUNCtion パラメータへ変換する。

    Args:
        mode: ctrl API 上の測定モード名である。

    Returns:
        SCPI FUNCtion に渡す関数名である。

    Raises:
        ValueError: 未対応の測定モードが指定された場合に送出する。
    """
    if mode not in MODE_TO_SCPI_FUNCTION:
        raise ValueError("未対応の測定モードである: {0!r}".format(mode))
    return MODE_TO_SCPI_FUNCTION[mode]


def _validate_integration_speed(speed):
    """XDM1000 の RATE パラメータを検証する。

    Args:
        speed: 積分速度である。F、M、S のいずれかを指定する。

    Returns:
        大文字化した積分速度文字列である。

    Raises:
        ValueError: F、M、S 以外が指定された場合に送出する。
    """
    speed = str(speed).upper()
    if speed not in ("F", "M", "S"):
        raise ValueError(
            "integration_speed は 'F', 'M', 'S' のいずれかでなければならない。"
        )
    return speed


def _continuous_result(
    job_id,
    ok,
    stopped,
    mode,
    range_value,
    range_index,
    range_label,
    auto_range,
    integration_speed,
    interval,
    duration,
    count_limit,
    samples,
    started_at,
    finished_at=None,
):
    """連続測定結果 dict を作成する。

    測定中も終了後も同じ構造を使う。get_result() はこの dict を返す。
    finished_at が None の間は running=True として扱う。

    Args:
        job_id: 連続測定ジョブを識別する ID である。
        ok: 測定結果が正常であるかどうかを表す。
        stopped: stop() により停止されたかどうかを表す。
        mode: 測定モード名である。
        range_value: 利用者が指定した物理量レンジである。
        range_index: SCPI RANGE 番号である。
        range_label: 表示用レンジラベルである。
        auto_range: オートレンジ状態である。
        integration_speed: 積分速度である。
        interval: 連続測定の測定間隔である。
        duration: 連続測定の最大測定時間である。
        count_limit: 連続測定の最大測定回数である。
        samples: 測定サンプル列である。
        started_at: 測定開始時刻である。
        finished_at: 測定終了時刻である。None の場合は測定中である。

    Returns:
        単発測定と区別可能な連続測定結果 dict である。
    """
    return {
        "type": "continuous",
        "job_id": job_id,
        "ok": ok,
        "running": finished_at is None,
        "stopped": stopped,
        "mode": mode,
        "range_value": range_value,
        "range_index": range_index,
        "range_label": range_label,
        "auto_range": auto_range,
        "integration_speed": integration_speed,
        "continue_interval": interval,
        "continue_duration": duration,
        "continue_count": count_limit,
        "started_at": started_at,
        "finished_at": finished_at,
        "samples": list(samples),
    }


def _worker_loop(
    command_q,
    response_q,
    state,
    result_store,
    stop_event,
    port,
    timeout,
    baudrate,
    logger=None,
    log_level=None,
    config=None,
):
    """測定ワーカープロセスの entry point である。

    Args:
        command_q: 親プロセスから worker へ送るコマンドキューである。
        response_q: worker から親プロセスへ返す応答キューである。
        state: worker の状態を共有する dict である。
        result_store: 直近測定結果を共有する dict である。
        stop_event: 連続測定停止要求を共有するイベントである。
        port: シリアルポート名である。
        timeout: シリアル通信タイムアウトである。
        baudrate: シリアル通信速度である。
        logger: worker へ渡す logger である。
        log_level: logger が未指定の場合に使うログレベルである。
        config: 設定オブジェクトである。
    """
    worker = _Xdm1000Worker(
        command_q=command_q,
        response_q=response_q,
        state=state,
        result_store=result_store,
        stop_event=stop_event,
        port=port,
        timeout=timeout,
        baudrate=baudrate,
        logger=logger,
        log_level=log_level,
        config=config,
    )
    worker.run()


class DeviceBusyError(RuntimeError):
    """測定器が長時間測定中のため、競合する要求を拒否したことを表す。"""

    pass


class DeviceWorkerError(RuntimeError):
    """測定ワーカープロセス側で例外が発生したことを表す。"""

    pass


class Xdm1000Ctrl(object):
    """XDM1000 / XDM1241 を測定器として扱う上位制御クラスである。

    SCPI の薄いラッパではなく、測定モード、レンジ、積分速度、
    連続測定条件を保持する利用者向け API を提供する。use_process=True
    では worker プロセスを介して測定器へアクセスし、use_process=False
    では同一プロセス内で SCPI クラスを直接使う。
    """

    def __init__(
        self,
        port=None,
        timeout=2.0,
        baudrate=115200,
        logger=None,
        log_level=None,
        config=None,
        use_process=True,
    ):
        """上位制御クラスを初期化する。

        Args:
            port: シリアルポート名である。config が指定されている場合は
                config.PORT が優先される。
            timeout: シリアル通信タイムアウトである。
            baudrate: シリアル通信速度である。
            logger: 利用する logger である。None の場合は標準 logging から
                モジュール logger を作成する。
            log_level: logger 作成時に使うログレベルである。
            config: 設定オブジェクトである。指定時は PORT、TIMEOUT、
                BAUDRATE をこのオブジェクトから取得する。
            use_process: True の場合は worker プロセス経由、False の場合は
                direct SCPI モードで動作する。

        Raises:
            ValueError: port が指定されず、config からも取得できない場合に
                送出する。
        """
        if logger is None:
            import logging

            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            logger = logging.getLogger(__name__)

        self.logger = logger
        self.log_level = log_level
        self.config = config
        self.use_process = bool(use_process)

        # config が指定された場合は、コンストラクタ引数より config 側の値を優先する。
        if self.config is not None:
            port = getattr(self.config, "PORT", port)
            timeout = getattr(self.config, "TIMEOUT", timeout)
            baudrate = getattr(self.config, "BAUDRATE", baudrate)

        if port is None:
            raise ValueError("port が必要である。")

        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate

        self._mode = None
        self._range_value = None
        self._range_index = None
        self._range_label = None
        self._auto_range = None
        self._integration_speed = None
        self._continue_interval = 0.0
        self._continue_duration = None
        self._continue_count = None
        self._latest_result = None
        self._direct_stop_requested = False

        # use_process=False では Manager を使わないため、同等の状態を通常 dict に保持する。
        self._direct_state = {
            "worker_alive": False,
            "port": self.port,
            "baudrate": self.baudrate,
            "running": False,
            "job_id": None,
            "job_type": None,
            "started_at": None,
            "finished_at": None,
            "error": None,
            "traceback": None,
            "message": "direct_scpi_mode",
        }
        self._direct_result_store = {"result": None}  # type: Dict[str, object]

        # use_process=True 用のプロセス間共有オブジェクトである。
        self.scpi = None
        self._manager = None
        self._state = None
        self._result_store = None
        self._command_q = None
        self._response_q = None
        self._stop_event = None
        self._rpc_lock = None
        self._process = None

        if self.use_process:
            # 測定器アクセスを worker に集約し、親側からは RPC 風に操作する。
            self._manager = mp.Manager()
            self._state = self._manager.dict()
            self._result_store = self._manager.dict()
            self._result_store["result"] = None
            self._command_q = mp.Queue()
            self._response_q = mp.Queue()
            self._stop_event = mp.Event()
            self._rpc_lock = mp.Lock()

            self._process = mp.Process(
                target=_worker_loop,
                kwargs={
                    "command_q": self._command_q,
                    "response_q": self._response_q,
                    "state": self._state,
                    "result_store": self._result_store,
                    "stop_event": self._stop_event,
                    "port": self.port,
                    "timeout": self.timeout,
                    "baudrate": self.baudrate,
                    "logger": None,
                    "log_level": self.log_level,
                    "config": self.config,
                },
                daemon=True,
            )
            self._process.start()
            self._wait_worker_ready()
        else:
            # direct SCPI モードでは同一プロセス内で測定器へ直接アクセスする。
            self.scpi = Xdm1000Scpi(
                port=self.port,
                timeout=self.timeout,
                baudrate=self.baudrate,
                logger=self.logger,
                log_level=self.log_level,
                config=self.config,
            )
            self.scpi.remote()
            self._publish_direct_state()

    def _wait_worker_ready(self, timeout=5.0, poll_interval=0.05):
        """worker 起動完了または起動失敗を待つ。

        Args:
            timeout: 起動完了を待つ最大秒数である。
            poll_interval: 共有 state を確認する間隔である。

        Raises:
            RuntimeError: worker が起動失敗または起動直後に終了した場合に送出する。
            TimeoutError: timeout 以内に worker_alive が立たない場合に送出する。
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._state.get("worker_alive", False):
                return
            if self._state.get("error"):
                raise RuntimeError(
                    "worker 起動失敗: {0}\n{1}".format(
                        self._state.get("error"),
                        self._state.get("traceback", ""),
                    )
                )
            if self._process is not None and not self._process.is_alive():
                raise RuntimeError("worker process が起動直後に終了した。")
            time.sleep(poll_interval)
        raise TimeoutError("worker 起動 timeout")

    def _publish_direct_state(self):
        """direct モードの設定状態を state に反映する。

        use_process=False では worker 共有 state が存在しないため、
        get_state() が返す状態を _direct_state に集約する。
        """
        self._direct_state["mode"] = self._mode
        self._direct_state["range_value"] = self._range_value
        self._direct_state["range_index"] = getattr(self, "_range_index", None)
        self._direct_state["range_label"] = getattr(self, "_range_label", None)
        self._direct_state["auto_range"] = self._auto_range
        self._direct_state["integration_speed"] = self._integration_speed
        self._direct_state["continue_interval"] = self._continue_interval
        self._direct_state["continue_duration"] = self._continue_duration
        self._direct_state["continue_count"] = self._continue_count
        self._direct_state["stop_requested"] = self._direct_stop_requested
        self._direct_state["worker_alive"] = self.scpi is not None

    def _is_running(self):
        """長時間測定中かどうかを返す。

        Returns:
            連続測定ジョブが実行中なら True を返す。
        """
        if self.use_process:
            return bool(self._state.get("running", False))
        return bool(self._direct_state.get("running", False))

    def _require_not_running(self):
        """測定中なら設定変更や単発測定を拒否する。

        Raises:
            DeviceBusyError: 連続測定中に競合する操作が要求された場合に送出する。
        """
        if self._is_running():
            state = self.get_state()
            raise DeviceBusyError(
                "測定器は running 中である: job_type={0}, job_id={1}".format(
                    state.get("job_type"),
                    state.get("job_id"),
                )
            )

    def _rpc(self, name, args=None, timeout=None):
        """親プロセスから測定ワーカーへ 1 コマンドを送る。

        Args:
            name: worker に送るコマンド名である。
            args: worker コマンドへ渡す引数 dict である。
            timeout: 応答待ちの最大秒数である。None の場合は無期限に待つ。

        Returns:
            worker が返した result である。

        Raises:
            RuntimeError: direct モードで呼ばれた場合、または応答 ID が
                一致しない場合に送出する。
            TimeoutError: worker 応答が timeout 以内に返らない場合に送出する。
            DeviceWorkerError: worker 側で例外が発生した場合に送出する。
        """
        if not self.use_process:
            raise RuntimeError("use_process=False では _rpc は使わない。")

        req_id = uuid.uuid4().hex
        # 同時 RPC で response_q の応答対応が崩れないよう、親側で 1 本化する。
        with self._rpc_lock:
            self._command_q.put({"req_id": req_id, "cmd": name, "args": args or {}})
            if timeout is None:
                deadline = None
            else:
                deadline = time.time() + timeout

            while True:
                if deadline is None:
                    remaining = None
                else:
                    remaining = max(0.0, deadline - time.time())
                if deadline is not None and remaining <= 0.0:
                    raise TimeoutError("worker 応答待ち timeout: {0!r}".format(name))
                try:
                    response = self._response_q.get(timeout=remaining)
                except queue.Empty:
                    raise TimeoutError("worker 応答待ち timeout: {0!r}".format(name))
                if response.get("req_id") != req_id:
                    # 想定外の応答順序は、キュー対応関係の破綻として扱う。
                    raise RuntimeError(
                        "worker response の req_id が一致しない: {0!r}".format(response)
                    )
                if response.get("ok"):
                    self._sync_from_worker_state()
                    return response.get("result")
                raise DeviceWorkerError(
                    "{0}\n{1}".format(
                        response.get("error"), response.get("traceback", "")
                    )
                )

    def _sync_from_worker_state(self):
        """worker 共有 state を親側キャッシュへ反映する。

        worker 側で確定した測定モード、レンジ、積分速度、連続測定条件、
        直近結果を親側属性へ同期する。direct モードでは何もしない。
        """
        if not self.use_process:
            return
        self._mode = self._state.get("mode")
        self._range_value = self._state.get("range_value")
        self._range_index = self._state.get("range_index")
        self._range_label = self._state.get("range_label")
        self._auto_range = self._state.get("auto_range")
        self._integration_speed = self._state.get("integration_speed")
        self._continue_interval = self._state.get("continue_interval", 0.0)
        self._continue_duration = self._state.get("continue_duration")
        self._continue_count = self._state.get("continue_count")
        self._latest_result = self._result_store.get("result")

    def _require_mode_direct(self):
        """direct モードで測定モード未設定なら例外にする。"""
        if self._mode is None:
            raise ValueError("先に set_mode() で測定モードを設定する必要がある。")

    def close(self):
        """接続または worker を閉じる。

        worker プロセス利用時は shutdown RPC を試み、応答しない場合は
        terminate する。direct モードでは測定器を local に戻してから
        シリアル接続を閉じる。
        """
        if self.use_process:
            if self._process is not None and self._process.is_alive():
                try:
                    self._rpc("shutdown", timeout=2.0)
                except Exception:
                    pass
                self._process.join(timeout=2.0)
                if self._process.is_alive():
                    self._process.terminate()
                    self._process.join(timeout=2.0)
            if self._manager is not None:
                try:
                    self._manager.shutdown()
                except Exception:
                    pass
        else:
            if self.scpi is not None:
                try:
                    self.scpi.local()
                except Exception:
                    pass
                try:
                    self.scpi.close()
                except Exception:
                    pass
                self.scpi = None
                self._publish_direct_state()

    def disconnect(self):
        """close の別名である。"""
        self.close()

    def get_state(self):
        """現在の状態を返す。

        Returns:
            測定モード、レンジ、連続測定状態、worker 生存状態などを含む
            状態 dict である。
        """
        if self.use_process:
            state = dict(self._state)
            state["process_alive"] = self._process.is_alive()
            return state
        state = dict(self._direct_state)
        state["process_alive"] = False
        return state

    def is_running(self):
        """長時間測定中なら True を返す。"""
        return self._is_running()

    def stop(self):
        """現在実行中の測定に停止要求を出す。

        この API は即時 kill ではない。連続測定ループが次に停止要求を
        確認した時点で終了する。停止対象がない場合は何もしない。
        """
        if not self._is_running():
            return {
                "stopping": False,
                "running": False,
                "message": "not running",
            }

        if self.use_process:
            self._stop_event.set()
            self._state["stop_requested"] = True
            self._state["message"] = "stop requested"
            return {
                "stopping": True,
                "running": True,
                "message": "stop requested",
            }

        self._direct_stop_requested = True
        self._direct_state["stop_requested"] = True
        self._direct_state["message"] = "stop requested"
        return {
            "stopping": True,
            "running": True,
            "message": "stop requested",
        }

    def idn(self):
        """*IDN? を返す。

        Returns:
            測定器が返す識別文字列である。

        Raises:
            DeviceBusyError: 連続測定中に呼ばれた場合に送出する。
        """
        self._require_not_running()
        if self.use_process:
            return self._rpc("idn", timeout=5.0)
        return self.scpi.idn()

    def _reset_scpi_internal(self):
        """内部確認用に *RST を実行する。"""
        self._require_not_running()
        if self.use_process:
            result = self._rpc("reset", timeout=10.0)
            self._sync_from_worker_state()
            return result
        self.scpi.reset()
        self._mode = None
        self._range_value = None
        self._range_index = None
        self._range_label = None
        self._auto_range = None
        self._integration_speed = None
        self._latest_result = None
        self._direct_result_store["result"] = None
        self._publish_direct_state()
        return None

    def set_mode(self, mode):
        """測定モードを設定する。

        Args:
            mode: ctrl API 上の測定モード名である。

        Returns:
            設定した測定モードを含む dict、または worker 側 result である。

        Raises:
            ValueError: 未対応の測定モードが指定された場合に送出する。
            DeviceBusyError: 連続測定中に呼ばれた場合に送出する。
        """
        self._require_not_running()
        _validate_mode(mode)
        if self.use_process:
            return self._rpc("set_mode", {"mode": mode}, timeout=10.0)
        self.scpi.set_function(MODE_TO_SCPI_FUNCTION[mode])
        self._mode = mode
        self._range_value = None
        self._range_index = None
        self._range_label = None
        self._auto_range = None
        self._publish_direct_state()
        return {"mode": mode}

    def set_range(self, value=None, index=None, range_value=None):
        """現在の測定モードに対する手動レンジを設定する。

        value は物理量指定である。数値は現在の測定モードの基本単位として
        扱う。電圧系では V、電流系では A、抵抗系では Ohm、静電容量では
        F である。単位付き文字列は "500 mV" と "500mV" の両方を
        受け付ける。

        index は SCPI RANGE 離散番号を直接指定する。value、index、
        range_value は同時に指定できない。range_value は旧 API 互換の
        物理量指定であり、value と同じ意味で扱う。
        """
        self._require_not_running()

        # value/range_value は物理量指定、index は RANGE 番号直接指定であり、混在させない。
        specified = []
        if value is not None:
            specified.append("value")
        if index is not None:
            specified.append("index")
        if range_value is not None:
            specified.append("range_value")
        if len(specified) != 1:
            raise ValueError(
                "set_range() は value, index, range_value のいずれか1つだけを指定する。"
            )

        mode = self._mode
        if index is not None:
            range_index, range_label = _validate_range_index(mode, index)
            stored_value = None
        else:
            if range_value is not None:
                value = range_value
            range_index, range_label = _parse_range_quantity(mode, value)
            stored_value = value

        if self.use_process:
            # worker 側 SCPI API は RANGE 番号で設定するため、親側で物理量を番号へ解決してから送る。
            result = self._rpc("set_range", {"range_value": range_index}, timeout=10.0)
            self._range_value = stored_value
            self._range_index = range_index
            self._range_label = range_label
            self._auto_range = False
            return {
                "range_value": stored_value,
                "range_index": range_index,
                "range_label": range_label,
                "auto_range": False,
                "worker_result": result,
            }
        self._require_mode_direct()
        self.scpi.set_range(range_index)
        self._range_value = stored_value
        self._range_index = range_index
        self._range_label = range_label
        self._auto_range = False
        self._publish_direct_state()
        return {
            "range_value": stored_value,
            "range_index": range_index,
            "range_label": range_label,
        }

    def set_auto_range(self, enabled):
        """オートレンジを設定する。

        Args:
            enabled: True の場合はオートレンジを有効にし、False の場合は
                現在保持している手動レンジへ戻す。

        Returns:
            オートレンジ状態を含む dict、または worker 側 result である。

        Raises:
            ValueError: 手動レンジ未設定の状態で False が指定された場合に送出する。
            DeviceBusyError: 連続測定中に呼ばれた場合に送出する。
        """
        self._require_not_running()
        if self.use_process:
            return self._rpc("set_auto_range", {"enabled": bool(enabled)}, timeout=10.0)
        self._require_mode_direct()
        if bool(enabled):
            self.scpi.set_auto_range(True)
            self._auto_range = True
        else:
            if self._range_index is None:
                raise ValueError(
                    "auto_range=False にするには、先に set_range() で手動レンジを設定する必要がある。"
                )
            self.scpi.set_range(self._range_index)
            self._auto_range = False
        self._publish_direct_state()
        return {"auto_range": self._auto_range}

    def set_integration_speed(self, speed):
        """内部測定速度を設定する。speed は F/M/S である。"""
        self._require_not_running()
        speed = _validate_integration_speed(speed)
        if self.use_process:
            return self._rpc("set_integration_speed", {"speed": speed}, timeout=10.0)
        self.scpi.set_rate(speed)
        self._integration_speed = speed
        self._publish_direct_state()
        return {"integration_speed": speed}

    def set_continue_interval(self, interval):
        """連続測定の測定間隔を設定する。"""
        self._require_not_running()
        interval = float(interval)
        if interval < 0.0:
            raise ValueError("interval は 0 以上でなければならない。")
        if self.use_process:
            return self._rpc(
                "set_continue_interval", {"interval": interval}, timeout=5.0
            )
        self._continue_interval = interval
        self._publish_direct_state()
        return {"continue_interval": interval}

    def set_continue_duration(self, duration):
        """連続測定の最大測定時間を設定する。None で無効化する。"""
        self._require_not_running()
        if duration is not None:
            duration = float(duration)
            if duration <= 0.0:
                raise ValueError("duration は正の値でなければならない。")
        if self.use_process:
            return self._rpc(
                "set_continue_duration", {"duration": duration}, timeout=5.0
            )
        self._continue_duration = duration
        self._publish_direct_state()
        return {"continue_duration": duration}

    def set_continue_count(self, count):
        """連続測定の最大測定回数を設定する。None で無効化する。"""
        self._require_not_running()
        if count is not None:
            count = int(count)
            if count <= 0:
                raise ValueError("count は正の整数でなければならない。")
        if self.use_process:
            return self._rpc("set_continue_count", {"count": count}, timeout=5.0)
        self._continue_count = count
        self._publish_direct_state()
        return {"continue_count": count}

    def meas(self, wait=None):
        """現在設定で 1 回測定する。"""
        self._require_not_running()
        if self.use_process:
            result = self._rpc(
                "meas", {"wait": wait}, timeout=10.0 + max(0.0, float(wait or 0.0))
            )
            self._latest_result = result
            return result

        self._require_mode_direct()
        if wait is not None:
            wait = float(wait)
            if wait > 0.0:
                time.sleep(wait)
        t0 = time.perf_counter()
        before = time.time()
        value = self.scpi.meas_main()
        after = time.time()
        result = {
            "type": "single",
            "mode": self._mode,
            "range_value": self._range_value,
            "range_index": self._range_index,
            "range_label": self._range_label,
            "auto_range": self._auto_range,
            "integration_speed": self._integration_speed,
            "value": value,
            "host_time_start": before,
            "host_time_end": after,
            "read_elapsed": time.perf_counter() - t0,
        }
        self._latest_result = result
        self._direct_result_store["result"] = result
        return result

    def _direct_begin_job(self, job_id, job_type):
        """direct モードの長時間測定開始状態を設定する。"""
        self._direct_stop_requested = False
        self._direct_state["stop_requested"] = False
        self._direct_state["running"] = True
        self._direct_state["job_id"] = job_id
        self._direct_state["job_type"] = job_type
        self._direct_state["started_at"] = time.time()
        self._direct_state["finished_at"] = None
        self._direct_state["error"] = None
        self._direct_state["traceback"] = None

    def _direct_finish_job(self):
        """direct モードの長時間測定終了状態を設定する。"""
        self._direct_stop_requested = False
        self._direct_state["stop_requested"] = False
        self._direct_state["running"] = False
        self._direct_state["job_id"] = None
        self._direct_state["job_type"] = None
        self._direct_state["finished_at"] = time.time()

    def meas_continue(self, wait=None):
        """現在設定で連続測定する。

        set_continue_duration() または set_continue_count() で設定された終了条件に
        到達するまで、現在の測定モードで繰り返し測定する。direct モードでは
        同期的に測定ループを実行し、測定中の途中結果も result store に反映する。

        Args:
            wait: 測定開始前に待つ秒数である。None の場合は待たない。

        Returns:
            連続測定ジョブ ID を含む dict、または worker 側 result である。

        Raises:
            ValueError: 連続測定の終了条件が未設定の場合に送出する。
            DeviceBusyError: 既に測定中の場合に送出する。
        """
        self._require_not_running()
        # duration と count のどちらも未設定の場合、終了条件がないため連続測定を開始しない。
        if self._continue_duration is None and self._continue_count is None:
            raise ValueError(
                "meas_continue() の前に set_continue_duration() または set_continue_count() を設定する必要がある。"
            )

        if self.use_process:
            self._stop_event.clear()
            job_id = uuid.uuid4().hex
            result = self._rpc(
                "meas_continue",
                {"job_id": job_id, "wait": wait},
                timeout=10.0 + max(0.0, float(wait or 0.0)),
            )
            return result

        self._require_mode_direct()
        if wait is not None:
            wait = float(wait)
            if wait > 0.0:
                time.sleep(wait)

        job_id = uuid.uuid4().hex
        self._direct_begin_job(job_id, "continuous")
        interval = float(self._continue_interval or 0.0)
        duration = self._continue_duration
        count_limit = self._continue_count
        samples = []
        t0 = time.perf_counter()
        deadline = None
        # duration は perf_counter 基準で判定し、システム時刻変更の影響を避ける。
        if duration is not None:
            deadline = t0 + float(duration)

        try:
            index = 0
            while True:
                if self._direct_stop_requested:
                    break
                now = time.perf_counter()
                if deadline is not None and now >= deadline:
                    break
                if count_limit is not None and index >= count_limit:
                    break
                before_perf = time.perf_counter()
                before = time.time()
                value = self.scpi.meas_main()
                after = time.time()
                after_perf = time.perf_counter()
                samples.append(
                    {
                        "index": index,
                        "value": value,
                        "host_time_start": before,
                        "host_time_end": after,
                        "read_elapsed": after_perf - before_perf,
                        "t_rel_start": before_perf - t0,
                        "t_rel_end": after_perf - t0,
                    }
                )
                index += 1

                # 測定中でも get_result() から途中結果を取得できるよう、サンプルごとに更新する。
                self._direct_result_store["result"] = _continuous_result(
                    job_id=job_id,
                    ok=True,
                    stopped=False,
                    mode=self._mode,
                    range_value=self._range_value,
                    range_index=self._range_index,
                    range_label=self._range_label,
                    auto_range=self._auto_range,
                    integration_speed=self._integration_speed,
                    interval=interval,
                    duration=duration,
                    count_limit=count_limit,
                    samples=samples,
                    started_at=self._direct_state.get("started_at"),
                    finished_at=None,
                )
                self._latest_result = self._direct_result_store["result"]
                self._direct_state["sample_count"] = len(samples)
                self._direct_state["latest_value"] = value
                self._direct_state["latest_host_time"] = after
                self._direct_state["elapsed"] = after_perf - t0

                if interval > 0.0:
                    # 測定開始時刻を基準に次回タイミングを作り、読み取り時間分の遅れを抑える。
                    next_target = before_perf + interval
                    while True:
                        if self._direct_stop_requested:
                            break
                        remain = next_target - time.perf_counter()
                        if remain <= 0.0:
                            break
                        time.sleep(min(remain, 0.001))
            # ループ終了時は finished_at を入れ、running=False の結果として保存する。
            result = _continuous_result(
                job_id=job_id,
                ok=True,
                stopped=self._direct_stop_requested,
                mode=self._mode,
                range_value=self._range_value,
                range_index=self._range_index,
                range_label=self._range_label,
                auto_range=self._auto_range,
                integration_speed=self._integration_speed,
                interval=interval,
                duration=duration,
                count_limit=count_limit,
                samples=samples,
                started_at=self._direct_state.get("started_at"),
                finished_at=time.time(),
            )
            self._latest_result = result
            self._direct_result_store["result"] = result
            self._direct_finish_job()
            return {"job_id": job_id}
        except BaseException:
            self._direct_state["running"] = False
            self._direct_state["error"] = "meas_continue failed"
            self._direct_state["traceback"] = ""
            self._direct_finish_job()
            raise

    def get_result(self, clear=False):
        """直近の単発測定または連続測定結果を返す。

        Args:
            clear: True の場合は、取得後に result store を None に戻す。

        Returns:
            直近の測定結果 dict である。結果がまだない場合は None を返す。
        """
        if self.use_process:
            result = self._result_store.get("result")
            if clear:
                self._result_store["result"] = None
            self._latest_result = result
            return result
        result = self._direct_result_store.get("result")
        if clear:
            self._direct_result_store["result"] = None
            self._latest_result = None
        return result

    def wait_until_done(self, poll_interval=0.2):
        """running が終わるまで待つ。

        Args:
            poll_interval: get_state() を呼び直す間隔である。

        Returns:
            running が False になった時点の状態 dict である。
        """
        while True:
            state = self.get_state()
            if not state.get("running", False):
                return state
            time.sleep(poll_interval)


def main(config_path="xdm1000_example.yml"):
    """ctrl クラス単独の動作確認用サンプルである。

    Args:
        config_path: 動作確認に使う設定ファイルパスである。
    """
    config = None
    try:
        config = Config(config_path)
    except Exception:
        config = None

    # port = "/dev/cu.usbserial-10"
    port = "com8"
    if config is not None:
        port = getattr(config, "PORT", port)

    # dmm = Xdm1000Ctrl(
    #     port=port,
    #     timeout=2.0,
    #     baudrate=115200,
    #     use_process=False,
    # )
    dmm = Xdm1000Ctrl(config=config, use_process=False)
    try:
        print("IDN:", dmm.idn())
        # dmm.set_mode("voltage_dc")
        dmm.set_mode("current_dc")
        dmm.set_auto_range(True)
        dmm.set_integration_speed("F")

        for i in range(10):
            print(dmm.meas())

    finally:
        dmm.close()


if __name__ == "__main__":
    main()
