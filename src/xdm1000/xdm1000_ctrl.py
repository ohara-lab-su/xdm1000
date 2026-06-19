#!/usr/bin/env python3
"""High-level process-based controller for OWON XDM1000 series DMMs.

Design:
- No Python threads.
- A dedicated worker process owns the serial port for the lifetime of the controller.
- The parent process provides a server-safe API: state/result methods remain responsive.
- Measurement/configuration commands are rejected while a long measurement job is running.
- Long jobs:
  1. continuous measurement: host-timestamped MEAS1? samples for a specified duration.
  2. statistics test mode: CALCulate:FUNCtion AVERage and CALCulate:AVERage:ALL?.
  3. one-shot measurement: single MEAS1? read.
"""

from __future__ import annotations

import math
import multiprocessing as mp
import queue
import time
import traceback
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from .xdm1000_scpi import XDM1000SCPI


MeasureKind = Literal[
    "voltage_dc",
    "voltage_ac",
    "current_dc",
    "current_ac",
    "resistance",
    "fresistance",
    "frequency",
    "period",
    "capacitance",
    "temperature_rtd",
    "diode",
    "continuity",
]


class DeviceBusyError(RuntimeError):
    """Raised when a measurement/configuration request is made while running."""


class DeviceWorkerError(RuntimeError):
    """Raised when the worker process reports an error."""


@dataclass(frozen=True)
class MeasurementConfig:
    """Current measurement configuration."""

    kind: MeasureKind
    range_value: str | float | int = "AUTO"
    rate: str = "F"


def _now_sample_clock(t0_perf: float) -> dict[str, float]:
    perf = time.perf_counter()
    return {
        "host_time": time.time(),
        "host_perf": perf,
        "t_rel": perf - t0_perf,
    }


def _configure(scpi: XDM1000SCPI, kind: str, range_value: str | float | int) -> None:
    """Apply measurement configuration to the instrument."""
    if kind == "voltage_dc":
        scpi.configure_voltage_dc(range_value)
    elif kind == "voltage_ac":
        scpi.configure_voltage_ac(range_value)
    elif kind == "current_dc":
        scpi.configure_current_dc(range_value)
    elif kind == "current_ac":
        scpi.configure_current_ac(range_value)
    elif kind == "resistance":
        scpi.configure_resistance(range_value)
    elif kind == "fresistance":
        scpi.configure_fresistance(range_value)
    elif kind == "frequency":
        scpi.configure_frequency(range_value)
    elif kind == "period":
        scpi.configure_period(range_value)
    elif kind == "capacitance":
        scpi.configure_capacitance(range_value)
    elif kind == "temperature_rtd":
        scpi.configure_temperature_rtd()
    elif kind == "diode":
        scpi.configure_diode()
    elif kind == "continuity":
        scpi.configure_continuity()
    else:
        raise ValueError(f"Unsupported measurement kind: {kind!r}")


def _values_stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "minimum": None,
            "maximum": None,
            "average": None,
            "stdev_population": None,
        }
    count = len(values)
    avg = sum(values) / count
    var = sum((x - avg) ** 2 for x in values) / count
    return {
        "count": count,
        "minimum": min(values),
        "maximum": max(values),
        "average": avg,
        "stdev_population": math.sqrt(var),
    }


def _worker_loop(
    command_q: mp.Queue,
    response_q: mp.Queue,
    state: Any,
    result_store: Any,
    stop_event: mp.Event,
    port: str,
    baudrate: int,
    timeout: float,
    write_timeout: float | None,
    serial_kwargs: dict[str, Any],
) -> None:
    """Worker process main loop.

    Only this process owns the serial port.
    """
    scpi: XDM1000SCPI | None = None

    def set_idle() -> None:
        state["running"] = False
        state["job_id"] = None
        state["job_type"] = None
        state["started_at"] = None
        state["finished_at"] = None
        state["error"] = None
        state["message"] = "idle"

    def set_running(job_id: str, job_type: str) -> None:
        state["running"] = True
        state["job_id"] = job_id
        state["job_type"] = job_type
        state["started_at"] = time.time()
        state["finished_at"] = None
        state["error"] = None
        state["message"] = "running"

    def finish(message: str = "finished") -> None:
        state["running"] = False
        state["finished_at"] = time.time()
        state["message"] = message

    def fail(exc: BaseException) -> None:
        state["running"] = False
        state["finished_at"] = time.time()
        state["error"] = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        state["traceback"] = traceback.format_exc()
        state["message"] = "error"

    try:
        scpi = XDM1000SCPI(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
            write_timeout=write_timeout,
            **serial_kwargs,
        )
        set_idle()
        state["worker_alive"] = True
        state["port"] = port
    except BaseException as exc:
        state["worker_alive"] = False
        state["error"] = repr(exc)
        state["traceback"] = traceback.format_exc()
        return

    while True:
        try:
            cmd = command_q.get()
            req_id = cmd.get("req_id")
            name = cmd.get("cmd")
            args = cmd.get("args", {})
            try:
                if name == "shutdown":
                    response_q.put({"req_id": req_id, "ok": True, "result": None})
                    break

                if name == "idn":
                    response_q.put({"req_id": req_id, "ok": True, "result": scpi.idn()})

                elif name == "remote":
                    scpi.remote()
                    response_q.put({"req_id": req_id, "ok": True, "result": None})

                elif name == "local":
                    scpi.local()
                    response_q.put({"req_id": req_id, "ok": True, "result": None})

                elif name == "reset":
                    scpi.reset()
                    response_q.put({"req_id": req_id, "ok": True, "result": None})

                elif name == "set_measurement_mode":
                    _configure(scpi, args["kind"], args.get("range_value", "AUTO"))
                    scpi.set_rate(args.get("rate", "F"))
                    state["measurement_kind"] = args["kind"]
                    state["range_value"] = args.get("range_value", "AUTO")
                    state["rate"] = args.get("rate", "F")
                    response_q.put({"req_id": req_id, "ok": True, "result": dict(args)})

                elif name == "one_shot":
                    _configure(scpi, args["kind"], args.get("range_value", "AUTO"))
                    scpi.set_rate(args.get("rate", "F"))
                    t0 = time.perf_counter()
                    before = _now_sample_clock(t0)
                    value = scpi.measure_main()
                    after = _now_sample_clock(t0)
                    response_q.put({
                        "req_id": req_id,
                        "ok": True,
                        "result": {
                            "kind": args["kind"],
                            "range_value": args.get("range_value", "AUTO"),
                            "rate": args.get("rate", "F"),
                            "value": value,
                            "host_time_start": before["host_time"],
                            "host_time_end": after["host_time"],
                            "host_elapsed": after["host_perf"] - before["host_perf"],
                        },
                    })

                elif name == "start_continuous":
                    job_id = args["job_id"]
                    duration = float(args["duration"])
                    interval = float(args.get("interval", 0.0))
                    if duration <= 0:
                        raise ValueError("duration must be positive.")
                    set_running(job_id, "continuous")
                    stop_event.clear()
                    _configure(scpi, args["kind"], args.get("range_value", "AUTO"))
                    scpi.set_rate(args.get("rate", "F"))
                    state["measurement_kind"] = args["kind"]
                    state["range_value"] = args.get("range_value", "AUTO")
                    state["rate"] = args.get("rate", "F")
                    state["duration"] = duration
                    state["interval"] = interval
                    response_q.put({"req_id": req_id, "ok": True, "result": {"job_id": job_id}})

                    samples: list[dict[str, Any]] = []
                    t0 = time.perf_counter()
                    deadline = t0 + duration
                    idx = 0
                    try:
                        while time.perf_counter() < deadline and not stop_event.is_set():
                            sample_start = _now_sample_clock(t0)
                            raw = scpi.measure_main()
                            sample_end = _now_sample_clock(t0)
                            samples.append({
                                "index": idx,
                                "kind": args["kind"],
                                "value": raw,
                                "host_time_start": sample_start["host_time"],
                                "host_time_end": sample_end["host_time"],
                                "t_rel_start": sample_start["t_rel"],
                                "t_rel_end": sample_end["t_rel"],
                                "read_elapsed": sample_end["host_perf"] - sample_start["host_perf"],
                            })
                            idx += 1
                            state["sample_count"] = idx
                            state["last_value"] = raw
                            state["last_host_time"] = sample_end["host_time"]
                            if interval > 0:
                                sleep_until = sample_end["host_perf"] + interval
                                while time.perf_counter() < sleep_until:
                                    if stop_event.is_set():
                                        break
                                    time.sleep(min(0.005, sleep_until - time.perf_counter()))
                    except BaseException as exc:
                        result_store["continuous"] = {
                            "job_id": job_id,
                            "ok": False,
                            "error": repr(exc),
                            "traceback": traceback.format_exc(),
                            "samples": samples,
                        }
                        fail(exc)
                    else:
                        values = [float(s["value"]) for s in samples]
                        result_store["continuous"] = {
                            "job_id": job_id,
                            "ok": True,
                            "stopped": stop_event.is_set(),
                            "kind": args["kind"],
                            "range_value": args.get("range_value", "AUTO"),
                            "rate": args.get("rate", "F"),
                            "duration_requested": duration,
                            "interval_requested": interval,
                            "samples": samples,
                            "stats": _values_stats(values),
                            "started_at": state.get("started_at"),
                            "finished_at": time.time(),
                        }
                        finish("stopped" if stop_event.is_set() else "finished")

                elif name == "start_statistics":
                    job_id = args["job_id"]
                    duration = float(args["duration"])
                    if duration <= 0:
                        raise ValueError("duration must be positive.")
                    set_running(job_id, "statistics")
                    stop_event.clear()
                    _configure(scpi, args["kind"], args.get("range_value", "AUTO"))
                    scpi.set_rate(args.get("rate", "F"))
                    state["measurement_kind"] = args["kind"]
                    state["range_value"] = args.get("range_value", "AUTO")
                    state["rate"] = args.get("rate", "F")
                    state["duration"] = duration
                    response_q.put({"req_id": req_id, "ok": True, "result": {"job_id": job_id}})

                    try:
                        # Test implementation. The exact reset/start semantics of the XDM1000
                        # statistics engine are firmware-dependent and must be verified on hardware.
                        scpi.set_calc_function("AVERage")
                        t0 = time.perf_counter()
                        deadline = t0 + duration
                        while time.perf_counter() < deadline and not stop_event.is_set():
                            time.sleep(min(0.05, deadline - time.perf_counter()))
                        stats = scpi.get_average_all()
                        result_store["statistics"] = {
                            "job_id": job_id,
                            "ok": True,
                            "stopped": stop_event.is_set(),
                            "kind": args["kind"],
                            "range_value": args.get("range_value", "AUTO"),
                            "rate": args.get("rate", "F"),
                            "duration_requested": duration,
                            "stats": {
                                "minimum": stats.minimum,
                                "maximum": stats.maximum,
                                "average": stats.average,
                                "count": stats.count,
                            },
                            "note": (
                                "Statistics mode is a test wrapper around "
                                "CALCulate:FUNCtion AVERage and CALCulate:AVERage:ALL?. "
                                "The statistics reset/start timing must be verified on the device."
                            ),
                            "started_at": state.get("started_at"),
                            "finished_at": time.time(),
                        }
                        finish("stopped" if stop_event.is_set() else "finished")
                    except BaseException as exc:
                        result_store["statistics"] = {
                            "job_id": job_id,
                            "ok": False,
                            "error": repr(exc),
                            "traceback": traceback.format_exc(),
                        }
                        fail(exc)

                else:
                    raise ValueError(f"Unknown worker command: {name!r}")

            except BaseException as exc:
                response_q.put({
                    "req_id": req_id,
                    "ok": False,
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                })
        except BaseException:
            state["worker_loop_error"] = traceback.format_exc()

    try:
        if scpi is not None:
            scpi.close()
    finally:
        state["worker_alive"] = False


class XDM1000:
    """High-level controller for server use.

    The public API separates three measurement families:

    1. one_shot:
       blocking single read. Rejected while a long job is running.

    2. continuous:
       process-side repeated MEAS1? acquisition for a specified duration.
       Samples are host timestamped and stored in the worker result buffer.

    3. statistics:
       test wrapper around the instrument CALCulate:AVERage statistics function.
       This is intentionally not treated as a guaranteed duration-average until
       the firmware behavior is verified.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: float = 2.0,
        write_timeout: float | None = 2.0,
        **serial_kwargs: Any,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.serial_kwargs = dict(serial_kwargs)

        self._manager = mp.Manager()
        self._state = self._manager.dict()
        self._result_store = self._manager.dict()
        self._command_q: mp.Queue = mp.Queue()
        self._response_q: mp.Queue = mp.Queue()
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
                "port": port,
                "baudrate": baudrate,
                "timeout": timeout,
                "write_timeout": write_timeout,
                "serial_kwargs": self.serial_kwargs,
            },
            daemon=True,
        )
        self._process.start()

    # ------------------------------------------------------------------
    # Internal RPC
    # ------------------------------------------------------------------
    def _is_running(self) -> bool:
        return bool(self._state.get("running", False))

    def _require_not_running(self) -> None:
        if self._is_running():
            raise DeviceBusyError(
                f"Device is running: job_type={self._state.get('job_type')}, "
                f"job_id={self._state.get('job_id')}"
            )

    def _rpc(self, name: str, args: dict[str, Any] | None = None, timeout: float | None = None) -> Any:
        req_id = uuid.uuid4().hex
        with self._rpc_lock:
            self._command_q.put({"req_id": req_id, "cmd": name, "args": args or {}})
            deadline = None if timeout is None else time.time() + timeout
            while True:
                remaining = None if deadline is None else max(0.0, deadline - time.time())
                if deadline is not None and remaining <= 0:
                    raise TimeoutError(f"Timeout waiting for worker response to {name!r}.")
                try:
                    resp = self._response_q.get(timeout=remaining)
                except queue.Empty as exc:
                    raise TimeoutError(f"Timeout waiting for worker response to {name!r}.") from exc
                if resp.get("req_id") != req_id:
                    # With the rpc lock this should not occur. Treat as protocol error.
                    raise RuntimeError(f"Unexpected worker response: {resp!r}")
                if resp.get("ok"):
                    return resp.get("result")
                raise DeviceWorkerError(f"{resp.get('error')}\n{resp.get('traceback', '')}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def close(self) -> None:
        """Shutdown the worker process."""
        if self._process.is_alive():
            try:
                self._rpc("shutdown", timeout=2.0)
            except Exception:
                pass
            self._process.join(timeout=2.0)
            if self._process.is_alive():
                self._process.terminate()
                self._process.join(timeout=2.0)
        self._manager.shutdown()

    def __enter__(self) -> "XDM1000":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # State/result API allowed during long measurements
    # ------------------------------------------------------------------
    def get_state(self) -> dict[str, Any]:
        """Return current server-side measurement state."""
        state = dict(self._state)
        state["process_alive"] = self._process.is_alive()
        return state

    def is_running(self) -> bool:
        return self._is_running()

    def stop_job(self) -> dict[str, Any]:
        """Request cooperative stop of a long-running job."""
        self._stop_event.set()
        return self.get_state()

    def get_continuous_result(self, clear: bool = False) -> dict[str, Any] | None:
        result = self._result_store.get("continuous")
        if clear and "continuous" in self._result_store:
            del self._result_store["continuous"]
        return result

    def get_statistics_result(self, clear: bool = False) -> dict[str, Any] | None:
        result = self._result_store.get("statistics")
        if clear and "statistics" in self._result_store:
            del self._result_store["statistics"]
        return result

    # ------------------------------------------------------------------
    # Direct commands rejected while running
    # ------------------------------------------------------------------
    def idn(self) -> str:
        self._require_not_running()
        return self._rpc("idn", timeout=5.0)

    def remote(self) -> None:
        self._require_not_running()
        self._rpc("remote", timeout=5.0)

    def local(self) -> None:
        self._require_not_running()
        self._rpc("local", timeout=5.0)

    def reset(self) -> None:
        self._require_not_running()
        self._rpc("reset", timeout=10.0)

    def set_measurement_mode(
        self,
        kind: MeasureKind,
        range_value: str | float | int = "AUTO",
        rate: str = "F",
    ) -> dict[str, Any]:
        """Set DMM measurement function/range/rate."""
        self._require_not_running()
        return self._rpc(
            "set_measurement_mode",
            {"kind": kind, "range_value": range_value, "rate": rate},
            timeout=10.0,
        )

    def measure_one_shot(
        self,
        kind: MeasureKind,
        range_value: str | float | int = "AUTO",
        rate: str = "F",
    ) -> dict[str, Any]:
        """Perform one blocking single measurement."""
        self._require_not_running()
        return self._rpc(
            "one_shot",
            {"kind": kind, "range_value": range_value, "rate": rate},
            timeout=10.0,
        )

    # Short aliases
    def meas(
        self,
        kind: MeasureKind = "voltage_dc",
        range_value: str | float | int = "AUTO",
        rate: str = "F",
    ) -> dict[str, Any]:
        return self.measure_one_shot(kind=kind, range_value=range_value, rate=rate)

    def measure_voltage_dc(self, range_value: str | float | int = "AUTO", rate: str = "F") -> dict[str, Any]:
        return self.measure_one_shot("voltage_dc", range_value, rate)

    def measure_current_dc(self, range_value: str | float | int = "AUTO", rate: str = "F") -> dict[str, Any]:
        return self.measure_one_shot("current_dc", range_value, rate)

    # ------------------------------------------------------------------
    # Long measurement jobs
    # ------------------------------------------------------------------
    def start_continuous_measurement(
        self,
        kind: MeasureKind,
        duration: float,
        range_value: str | float | int = "AUTO",
        rate: str = "F",
        interval: float = 0.0,
    ) -> dict[str, Any]:
        """Start process-side repeated MEAS1? acquisition.

        interval=0 means acquire as fast as the instrument/serial link allows.
        The method returns immediately after the worker has accepted the job.
        """
        self._require_not_running()
        job_id = uuid.uuid4().hex
        return self._rpc(
            "start_continuous",
            {
                "job_id": job_id,
                "kind": kind,
                "duration": duration,
                "range_value": range_value,
                "rate": rate,
                "interval": interval,
            },
            timeout=10.0,
        )

    def start_statistics_mode(
        self,
        kind: MeasureKind,
        duration: float,
        range_value: str | float | int = "AUTO",
        rate: str = "F",
    ) -> dict[str, Any]:
        """Start test statistics job using CALCulate:AVERage:ALL?.

        This is a test mode. It must not be treated as a guaranteed time-window
        average until the statistics reset/start semantics are verified on the
        physical XDM1000/XDM1241.
        """
        self._require_not_running()
        job_id = uuid.uuid4().hex
        return self._rpc(
            "start_statistics",
            {
                "job_id": job_id,
                "kind": kind,
                "duration": duration,
                "range_value": range_value,
                "rate": rate,
            },
            timeout=10.0,
        )


XDM1241 = XDM1000
