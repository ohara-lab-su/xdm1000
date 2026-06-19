#!/usr/bin/env python3
"""XDM1000 / XDM1241 用の上位制御クラスである。

この層は SCPI コマンドの薄い別名ではなく、測定器として使うための API を提供する。
低レベル SCPI 実装は xdm1000_scpi.py 側に残す。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import threading
import time
from typing import Callable, Optional, Union

try:
    from xdm1000.xdm1000_scpi import XDM1000SCPI
except ImportError:
    try:
        from .xdm1000_scpi import XDM1000SCPI
    except ImportError:
        from xdm1000_scpi import XDM1000SCPI

ScpiValue = Union[str, int, float]
MeasurementCallback = Callable[["MeasurementSample"], None]


class MeasurementMode(str, Enum):
    """上位 API で扱う測定種別である。"""

    VOLTAGE_DC = "voltage_dc"
    VOLTAGE_AC = "voltage_ac"
    CURRENT_DC = "current_dc"
    CURRENT_AC = "current_ac"
    RESISTANCE = "resistance"
    FRESISTANCE = "fresistance"
    FREQUENCY = "frequency"
    PERIOD = "period"
    CAPACITANCE = "capacitance"
    TEMPERATURE_RTD = "temperature_rtd"
    DIODE = "diode"
    CONTINUITY = "continuity"


# 旧名互換である。
MeasureMode = MeasurementMode


@dataclass(frozen=True)
class MeasurementConfig:
    """上位層の測定条件である。"""

    mode: str = MeasurementMode.VOLTAGE_DC.value
    range_value: ScpiValue = "AUTO"
    rate: str = "M"
    settle_time: float = 0.2
    rtd_type: Optional[str] = None
    temperature_unit: Optional[str] = None
    continuity_threshold: Optional[ScpiValue] = None

    def to_dict(self) -> dict[str, object]:
        """JSON 化しやすい dict に変換する。"""
        return asdict(self)


# 旧名互換である。
MeasureConfig = MeasurementConfig


@dataclass(frozen=True)
class MeasurementSample:
    """1 点の測定結果である。"""

    index: int
    timestamp: float
    elapsed: float
    mode: str
    value: float

    def to_dict(self) -> dict[str, Union[int, float, str]]:
        """JSON 化しやすい dict に変換する。"""
        return asdict(self)


@dataclass(frozen=True)
class MeasurementStatus:
    """連続測定状態である。"""

    running: bool
    config: Optional[MeasurementConfig]
    interval: Optional[float]
    started_at: Optional[float]
    elapsed: float
    sample_count: int
    last_sample: Optional[MeasurementSample]
    last_error: Optional[str]

    def to_dict(self) -> dict[str, object]:
        """JSON 化しやすい dict に変換する。"""
        data = asdict(self)
        if self.config is not None:
            data["config"] = self.config.to_dict()
        if self.last_sample is not None:
            data["last_sample"] = self.last_sample.to_dict()
        return data


class XDM1000:
    """XDM1000 / XDM1241 の上位制御クラスである。

    インスタンス生成時に接続を開き、サーバープロセスが生きている間は接続を維持する。
    上位 API は測定条件の設定、1shot 測定、連続測定を中心にする。
    """

    def __init__(
        self,
        port: str,
        timeout: float = 1.0,
        baudrate: int = 115200,
        logger=None,
    ) -> None:
        """低レベル SCPI クラスと同じ引数で初期化し、即座に接続を開く。"""
        self.port = port
        self.timeout = timeout
        self.baudrate = baudrate
        self._logger = logger

        self._scpi: Optional[XDM1000SCPI] = None
        self._lock = threading.RLock()

        self._config = MeasurementConfig()
        self._continuous_thread: Optional[threading.Thread] = None
        self._continuous_stop = threading.Event()
        self._continuous_interval: Optional[float] = None
        self._continuous_started_at: Optional[float] = None
        self._continuous_samples: list[MeasurementSample] = []
        self._continuous_last_error: Optional[str] = None
        self._continuous_callback: Optional[MeasurementCallback] = None

        self.open()

    # ------------------------------------------------------------------
    # lifetime
    # ------------------------------------------------------------------

    def open(self) -> None:
        """シリアルポートを開く。すでに開いている場合は何もしない。"""
        with self._lock:
            if self._scpi is not None:
                return
            self._scpi = XDM1000SCPI(
                port=self.port,
                timeout=self.timeout,
                baudrate=self.baudrate,
                logger=self._logger,
            )

    def close(self) -> None:
        """連続測定を停止し、シリアルポートを閉じる。"""
        self.stop_continuous_measurement()
        with self._lock:
            if self._scpi is None:
                return
            self._scpi.close()
            self._scpi = None

    def disconnect(self) -> None:
        """サーバー停止時に呼ばれる解放用エイリアスである。"""
        self.close()

    def __enter__(self) -> "XDM1000":
        """with 文用のエントリである。"""
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """with 文終了時に接続を閉じる。"""
        self.close()

    @property
    def is_open(self) -> bool:
        """シリアルポートが開いているかを返す。"""
        return self._scpi is not None

    def _require_scpi(self) -> XDM1000SCPI:
        """低レベル SCPI インスタンスを返す。閉じていれば例外を投げる。"""
        if self._scpi is None:
            raise RuntimeError("XDM1000 is not open")
        return self._scpi

    # ------------------------------------------------------------------
    # basic controls
    # ------------------------------------------------------------------

    def idn(self) -> str:
        """機器識別文字列を取得する。"""
        with self._lock:
            return self._require_scpi().idn()

    def remote(self) -> None:
        """機器をリモート操作状態にする。"""
        with self._lock:
            self._require_scpi().remote()

    def local(self) -> None:
        """機器をローカル操作状態に戻す。"""
        with self._lock:
            self._require_scpi().local()

    def reset(self) -> None:
        """機器設定をリセットする。"""
        with self._lock:
            self._require_scpi().reset()

    def set_beeper(self, enabled: bool) -> None:
        """ブザーの ON/OFF を設定する。"""
        with self._lock:
            self._require_scpi().set_beeper(enabled)

    def get_beeper(self) -> bool:
        """ブザー状態を取得する。"""
        with self._lock:
            return self._require_scpi().get_beeper()

    # ------------------------------------------------------------------
    # measurement mode / range / rate
    # ------------------------------------------------------------------

    def set_measurement_mode(
        self,
        mode: Union[MeasurementMode, str],
        range_value: Optional[ScpiValue] = None,
        rate: Optional[str] = None,
        settle_time: Optional[float] = None,
        rtd_type: Optional[str] = None,
        temperature_unit: Optional[str] = None,
        continuity_threshold: Optional[ScpiValue] = None,
    ) -> dict[str, object]:
        """測定モードを設定する。

        range_value/rate/settle_time を省略した場合は現在の上位設定を維持する。
        """
        current = self._config
        config = MeasurementConfig(
            mode=self._normalize_mode(mode).value,
            range_value=current.range_value if range_value is None else range_value,
            rate=current.rate if rate is None else rate,
            settle_time=current.settle_time if settle_time is None else float(settle_time),
            rtd_type=current.rtd_type if rtd_type is None else rtd_type,
            temperature_unit=current.temperature_unit if temperature_unit is None else temperature_unit,
            continuity_threshold=(
                current.continuity_threshold if continuity_threshold is None else continuity_threshold
            ),
        )
        self._apply_config(config)
        return config.to_dict()

    def get_measurement_mode(self) -> str:
        """現在の上位測定モードを返す。"""
        return self._config.mode

    def set_range(self, range_value: ScpiValue) -> dict[str, object]:
        """現在の測定モードのレンジ値を設定する。"""
        return self.set_measurement_config(range_value=range_value)

    def get_range(self) -> ScpiValue:
        """上位層が保持しているレンジ値を返す。"""
        return self._config.range_value

    def set_rate(self, rate: str) -> dict[str, object]:
        """測定速度を設定する。"""
        return self.set_measurement_config(rate=rate)

    def get_rate(self) -> str:
        """機器から測定速度を取得する。"""
        with self._lock:
            return self._require_scpi().get_rate()

    def set_measurement_config(
        self,
        mode: Optional[Union[MeasurementMode, str]] = None,
        range_value: Optional[ScpiValue] = None,
        rate: Optional[str] = None,
        settle_time: Optional[float] = None,
        rtd_type: Optional[str] = None,
        temperature_unit: Optional[str] = None,
        continuity_threshold: Optional[ScpiValue] = None,
    ) -> dict[str, object]:
        """測定条件をまとめて設定する。"""
        current = self._config
        mode_value = current.mode if mode is None else self._normalize_mode(mode).value
        config = MeasurementConfig(
            mode=mode_value,
            range_value=current.range_value if range_value is None else range_value,
            rate=current.rate if rate is None else rate,
            settle_time=current.settle_time if settle_time is None else float(settle_time),
            rtd_type=current.rtd_type if rtd_type is None else rtd_type,
            temperature_unit=current.temperature_unit if temperature_unit is None else temperature_unit,
            continuity_threshold=(
                current.continuity_threshold if continuity_threshold is None else continuity_threshold
            ),
        )
        self._apply_config(config)
        return config.to_dict()

    def get_measurement_config(self) -> dict[str, object]:
        """現在の上位測定条件を返す。"""
        return self._config.to_dict()

    def configure_measurement(
        self,
        mode: Union[MeasurementMode, str],
        range_value: ScpiValue = "AUTO",
        rate: str = "M",
        settle_time: float = 0.2,
        rtd_type: Optional[str] = None,
    ) -> MeasurementConfig:
        """旧 API 互換の測定条件設定である。"""
        config = MeasurementConfig(
            mode=self._normalize_mode(mode).value,
            range_value=range_value,
            rate=rate,
            settle_time=float(settle_time),
            rtd_type=rtd_type,
        )
        self._apply_config(config)
        return config

    def _apply_config(self, config: MeasurementConfig) -> None:
        """MeasurementConfig を実機へ反映する。"""
        with self._lock:
            scpi = self._require_scpi()
            mode = MeasurementMode(config.mode)
            if mode is MeasurementMode.VOLTAGE_DC:
                scpi.configure_voltage_dc(config.range_value)
            elif mode is MeasurementMode.VOLTAGE_AC:
                scpi.configure_voltage_ac(config.range_value)
            elif mode is MeasurementMode.CURRENT_DC:
                scpi.configure_current_dc(config.range_value)
            elif mode is MeasurementMode.CURRENT_AC:
                scpi.configure_current_ac(config.range_value)
            elif mode is MeasurementMode.RESISTANCE:
                scpi.configure_resistance(config.range_value)
            elif mode is MeasurementMode.FRESISTANCE:
                scpi.configure_fresistance(config.range_value)
            elif mode is MeasurementMode.FREQUENCY:
                scpi.configure_frequency()
            elif mode is MeasurementMode.PERIOD:
                scpi.configure_period()
            elif mode is MeasurementMode.CAPACITANCE:
                scpi.configure_capacitance(config.range_value)
            elif mode is MeasurementMode.TEMPERATURE_RTD:
                scpi.configure_temperature_rtd(config.rtd_type)
                if config.temperature_unit is not None:
                    scpi.set_temperature_unit(config.temperature_unit)
            elif mode is MeasurementMode.DIODE:
                scpi.configure_diode()
            elif mode is MeasurementMode.CONTINUITY:
                scpi.configure_continuity()
                if config.continuity_threshold is not None:
                    scpi.set_continuity_threshold(config.continuity_threshold)
            else:
                raise ValueError(f"unsupported measurement mode: {mode}")

            if config.rate:
                scpi.set_rate(config.rate)

            self._config = config

        if config.settle_time > 0:
            time.sleep(config.settle_time)

    @staticmethod
    def _normalize_mode(mode: Union[MeasurementMode, str]) -> MeasurementMode:
        """測定種別を MeasurementMode に正規化する。"""
        if isinstance(mode, MeasurementMode):
            return mode
        value = str(mode).strip().lower().replace("-", "_").replace(":", "_").replace(" ", "_")
        aliases = {
            "v": MeasurementMode.VOLTAGE_DC,
            "volt": MeasurementMode.VOLTAGE_DC,
            "voltage": MeasurementMode.VOLTAGE_DC,
            "vdc": MeasurementMode.VOLTAGE_DC,
            "dcv": MeasurementMode.VOLTAGE_DC,
            "volt_dc": MeasurementMode.VOLTAGE_DC,
            "voltage_dc": MeasurementMode.VOLTAGE_DC,
            "vac": MeasurementMode.VOLTAGE_AC,
            "acv": MeasurementMode.VOLTAGE_AC,
            "volt_ac": MeasurementMode.VOLTAGE_AC,
            "voltage_ac": MeasurementMode.VOLTAGE_AC,
            "i": MeasurementMode.CURRENT_DC,
            "curr": MeasurementMode.CURRENT_DC,
            "current": MeasurementMode.CURRENT_DC,
            "idc": MeasurementMode.CURRENT_DC,
            "dci": MeasurementMode.CURRENT_DC,
            "current_dc": MeasurementMode.CURRENT_DC,
            "iac": MeasurementMode.CURRENT_AC,
            "aci": MeasurementMode.CURRENT_AC,
            "current_ac": MeasurementMode.CURRENT_AC,
            "ohm": MeasurementMode.RESISTANCE,
            "res": MeasurementMode.RESISTANCE,
            "resistance": MeasurementMode.RESISTANCE,
            "fres": MeasurementMode.FRESISTANCE,
            "fresistance": MeasurementMode.FRESISTANCE,
            "4w": MeasurementMode.FRESISTANCE,
            "4w_resistance": MeasurementMode.FRESISTANCE,
            "freq": MeasurementMode.FREQUENCY,
            "frequency": MeasurementMode.FREQUENCY,
            "period": MeasurementMode.PERIOD,
            "cap": MeasurementMode.CAPACITANCE,
            "capacitance": MeasurementMode.CAPACITANCE,
            "temp": MeasurementMode.TEMPERATURE_RTD,
            "temperature": MeasurementMode.TEMPERATURE_RTD,
            "temperature_rtd": MeasurementMode.TEMPERATURE_RTD,
            "diode": MeasurementMode.DIODE,
            "continuity": MeasurementMode.CONTINUITY,
            "cont": MeasurementMode.CONTINUITY,
        }
        try:
            return aliases[value]
        except KeyError as exc:
            raise ValueError(f"unsupported measurement mode: {mode}") from exc

    # ------------------------------------------------------------------
    # one-shot measurement
    # ------------------------------------------------------------------

    def read(self) -> float:
        """現在の測定設定のまま、主表示を 1 点読む。"""
        with self._lock:
            return self._require_scpi().measure_main()

    def meas(self) -> float:
        """現在の測定設定のまま、主表示を 1 点読む。read() の別名である。"""
        return self.read()

    def measure_one_shot(
        self,
        mode: Optional[Union[MeasurementMode, str]] = None,
        range_value: Optional[ScpiValue] = None,
        rate: Optional[str] = None,
        settle_time: Optional[float] = None,
        rtd_type: Optional[str] = None,
        temperature_unit: Optional[str] = None,
        continuity_threshold: Optional[ScpiValue] = None,
    ) -> float:
        """必要なら測定条件を変更してから 1 点測定する。"""
        if any(v is not None for v in [mode, range_value, rate, settle_time, rtd_type, temperature_unit, continuity_threshold]):
            self.set_measurement_config(
                mode=mode,
                range_value=range_value,
                rate=rate,
                settle_time=settle_time,
                rtd_type=rtd_type,
                temperature_unit=temperature_unit,
                continuity_threshold=continuity_threshold,
            )
        return self.read()

    def measure_voltage_dc(self, range_value: ScpiValue = "AUTO", rate: str = "M", settle_time: float = 0.2) -> float:
        """DC 電圧を 1 点測定する。"""
        return self.measure_one_shot(MeasurementMode.VOLTAGE_DC, range_value, rate, settle_time)

    def measure_voltage_ac(self, range_value: ScpiValue = "AUTO", rate: str = "M", settle_time: float = 0.2) -> float:
        """AC 電圧を 1 点測定する。"""
        return self.measure_one_shot(MeasurementMode.VOLTAGE_AC, range_value, rate, settle_time)

    def measure_current_dc(self, range_value: ScpiValue = "AUTO", rate: str = "M", settle_time: float = 0.2) -> float:
        """DC 電流を 1 点測定する。"""
        return self.measure_one_shot(MeasurementMode.CURRENT_DC, range_value, rate, settle_time)

    def measure_current_ac(self, range_value: ScpiValue = "AUTO", rate: str = "M", settle_time: float = 0.2) -> float:
        """AC 電流を 1 点測定する。"""
        return self.measure_one_shot(MeasurementMode.CURRENT_AC, range_value, rate, settle_time)

    def measure_resistance(self, range_value: ScpiValue = "AUTO", rate: str = "M", settle_time: float = 0.2) -> float:
        """2 線式抵抗を 1 点測定する。"""
        return self.measure_one_shot(MeasurementMode.RESISTANCE, range_value, rate, settle_time)

    def measure_fresistance(self, range_value: ScpiValue = "AUTO", rate: str = "M", settle_time: float = 0.2) -> float:
        """4 線式抵抗を 1 点測定する。"""
        return self.measure_one_shot(MeasurementMode.FRESISTANCE, range_value, rate, settle_time)

    def measure_frequency(self, rate: str = "M", settle_time: float = 0.2) -> float:
        """周波数を 1 点測定する。"""
        return self.measure_one_shot(MeasurementMode.FREQUENCY, rate=rate, settle_time=settle_time)

    def measure_period(self, rate: str = "M", settle_time: float = 0.2) -> float:
        """周期を 1 点測定する。"""
        return self.measure_one_shot(MeasurementMode.PERIOD, rate=rate, settle_time=settle_time)

    def measure_capacitance(self, range_value: ScpiValue = "AUTO", rate: str = "M", settle_time: float = 0.2) -> float:
        """静電容量を 1 点測定する。"""
        return self.measure_one_shot(MeasurementMode.CAPACITANCE, range_value, rate, settle_time)

    def measure_temperature_rtd(
        self,
        rtd_type: Optional[str] = None,
        unit: Optional[str] = None,
        rate: str = "M",
        settle_time: float = 0.2,
    ) -> float:
        """RTD 温度を 1 点測定する。"""
        return self.measure_one_shot(
            MeasurementMode.TEMPERATURE_RTD,
            rate=rate,
            settle_time=settle_time,
            rtd_type=rtd_type,
            temperature_unit=unit,
        )

    # ------------------------------------------------------------------
    # continuous measurement
    # ------------------------------------------------------------------

    def start_continuous_measurement(
        self,
        mode: Optional[Union[MeasurementMode, str]] = None,
        range_value: Optional[ScpiValue] = None,
        rate: Optional[str] = None,
        interval: float = 0.5,
        duration: Optional[float] = None,
        max_samples: Optional[int] = None,
        settle_time: Optional[float] = None,
        rtd_type: Optional[str] = None,
        temperature_unit: Optional[str] = None,
        continuity_threshold: Optional[ScpiValue] = None,
        clear_buffer: bool = True,
        callback: Optional[MeasurementCallback] = None,
    ) -> dict[str, object]:
        """バックグラウンド連続測定を開始する。"""
        if interval <= 0:
            raise ValueError("interval must be positive")
        if duration is not None and duration <= 0:
            raise ValueError("duration must be positive or None")
        if max_samples is not None and max_samples <= 0:
            raise ValueError("max_samples must be positive or None")

        self.stop_continuous_measurement()
        if any(v is not None for v in [mode, range_value, rate, settle_time, rtd_type, temperature_unit, continuity_threshold]):
            self.set_measurement_config(
                mode=mode,
                range_value=range_value,
                rate=rate,
                settle_time=settle_time,
                rtd_type=rtd_type,
                temperature_unit=temperature_unit,
                continuity_threshold=continuity_threshold,
            )

        with self._lock:
            if clear_buffer:
                self._continuous_samples = []
            self._continuous_interval = float(interval)
            self._continuous_started_at = time.time()
            self._continuous_last_error = None
            self._continuous_callback = callback
            self._continuous_stop.clear()
            self._continuous_thread = threading.Thread(
                target=self._continuous_loop,
                kwargs={"duration": duration, "max_samples": max_samples},
                name="XDM1000ContinuousMeasurement",
                daemon=True,
            )
            self._continuous_thread.start()
        return self.get_continuous_status()

    def _continuous_loop(self, duration: Optional[float], max_samples: Optional[int]) -> None:
        """バックグラウンド連続測定ループである。"""
        assert self._continuous_started_at is not None
        assert self._continuous_interval is not None
        started_at = self._continuous_started_at
        next_time = time.monotonic()
        index = 0

        while not self._continuous_stop.is_set():
            timestamp = time.time()
            elapsed = timestamp - started_at
            if duration is not None and elapsed >= duration:
                break
            if max_samples is not None and index >= max_samples:
                break
            try:
                with self._lock:
                    mode = self._config.mode
                    value = self._require_scpi().measure_main()
                sample = MeasurementSample(
                    index=index,
                    timestamp=timestamp,
                    elapsed=elapsed,
                    mode=mode,
                    value=value,
                )
                callback = self._continuous_callback
                with self._lock:
                    self._continuous_samples.append(sample)
                    self._continuous_last_error = None
                if callback is not None:
                    callback(sample)
                index += 1
            except Exception as exc:  # noqa: BLE001
                with self._lock:
                    self._continuous_last_error = f"{type(exc).__name__}: {exc}"
                break

            next_time += self._continuous_interval
            sleep_time = next_time - time.monotonic()
            if sleep_time > 0:
                self._continuous_stop.wait(sleep_time)
            else:
                next_time = time.monotonic()

        self._continuous_stop.set()

    def stop_continuous_measurement(self, timeout: float = 5.0) -> dict[str, object]:
        """バックグラウンド連続測定を停止する。"""
        thread = self._continuous_thread
        if thread is not None and thread.is_alive():
            self._continuous_stop.set()
            thread.join(timeout=timeout)
        with self._lock:
            if self._continuous_thread is not None and not self._continuous_thread.is_alive():
                self._continuous_thread = None
        return self.get_continuous_status()

    def get_continuous_status(self) -> dict[str, object]:
        """連続測定状態を返す。"""
        with self._lock:
            running = self._continuous_thread is not None and self._continuous_thread.is_alive()
            now = time.time()
            elapsed = 0.0
            if self._continuous_started_at is not None:
                elapsed = max(0.0, now - self._continuous_started_at)
            last_sample = self._continuous_samples[-1] if self._continuous_samples else None
            status = MeasurementStatus(
                running=running,
                config=self._config,
                interval=self._continuous_interval,
                started_at=self._continuous_started_at,
                elapsed=elapsed,
                sample_count=len(self._continuous_samples),
                last_sample=last_sample,
                last_error=self._continuous_last_error,
            )
        return status.to_dict()

    def get_continuous_samples(self, limit: Optional[int] = None, clear: bool = False) -> list[dict[str, Union[int, float, str]]]:
        """連続測定バッファを返す。"""
        with self._lock:
            if limit is None:
                samples = list(self._continuous_samples)
            else:
                samples = list(self._continuous_samples[-int(limit):])
            if clear:
                self._continuous_samples = []
        return [sample.to_dict() for sample in samples]

    def clear_continuous_samples(self) -> None:
        """連続測定バッファを空にする。"""
        with self._lock:
            self._continuous_samples = []

    # 旧名互換である。
    start_measurement = start_continuous_measurement
    stop_measurement = stop_continuous_measurement
    get_measurement_status = get_continuous_status
    get_measurement_samples = get_continuous_samples
    clear_measurement_samples = clear_continuous_samples

    # ------------------------------------------------------------------
    # low-level escape hatch
    # ------------------------------------------------------------------

    def raw_write(self, command: str) -> None:
        """低レベル SCPI コマンドをそのまま送る。"""
        with self._lock:
            self._require_scpi().write(command)

    def raw_query(self, command: str) -> str:
        """低レベル SCPI クエリをそのまま送る。"""
        with self._lock:
            return self._require_scpi().query(command)

    @property
    def scpi(self) -> XDM1000SCPI:
        """低レベル SCPI ドライバを返す。サーバー公開用ではなくローカルデバッグ用である。"""
        return self._require_scpi()


# 機種名で使いたい場合のエイリアスである。
XDM1241 = XDM1000
