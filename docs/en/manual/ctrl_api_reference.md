# ctrl API Reference

`xdm1000_ctrl.py` provides the user-facing high-level control API for the XDM1000 / XDM1241 instruments. The SCPI layer is a thin wrapper over SCPI commands; the ctrl layer organizes measurement mode, range, auto-ranging, internal measurement speed, and continuous-measurement settings into a higher-level API.

This reference describes the APIs documented for the current `xdm1000_ctrl.py`, `xdm1000_worker.py`, and `server_fastapi/spec.py`.

## Design Policy

Do not mix measurement settings into the arguments of `meas()` or `meas_continue()`. Configure the instrument first using `set_mode()`, `set_range()`, `set_auto_range()`, and `set_integration_speed()`.

Single and continuous measurements have separate entry points:

```python
result = dmm.meas()
job = dmm.meas_continue()
```

Set the sampling interval and termination conditions required only for continuous measurement using `set_continue_interval()`, `set_continue_duration()`, and `set_continue_count()`.

## Public API

The main user-facing APIs of the current `Xdm1000Ctrl` are:

```text
close()
disconnect()
get_state()
is_running()
idn()
set_mode(mode)
set_range(value=None, index=None, range_value=None)
set_auto_range(enabled)
set_integration_speed(speed)
set_continue_interval(interval)
set_continue_duration(duration)
set_continue_count(count)
meas(wait=None)
meas_continue(wait=None)
get_result(clear=False)
wait_until_done(poll_interval=0.2)
```

The following legacy APIs are absent from the current `Xdm1000Ctrl`:

```text
set_meas_mode()
meas_one_shot()
meas_voltage_dc()
meas_current_dc()
start_continuous_meas()
start_statistics_mode()
get_continuous_result()
get_statistics_result()
stop_job()
```

`remote()`, `local()`, `query()`, and `write()` are not exposed as ctrl APIs; they are the responsibility of the SCPI layer.

## Initializing Xdm1000Ctrl

```python
Xdm1000Ctrl(
    port=None,
    timeout=2.0,
    baudrate=115200,
    logger=None,
    log_level=None,
    config=None,
    use_process=True,
)
```

If `config` is supplied, `PORT`, `TIMEOUT`, and `BAUDRATE` from it take precedence. If `port` remains unspecified, `ValueError` is raised.

With `use_process=True`, the worker process owns the actual SCPI object. The parent sends commands to the worker and reads status and results from shared state and the result store.

With `use_process=False`, `Xdm1000Ctrl` owns the SCPI object directly in the same process.

## State and Lifecycle

### close()

Closes the connection or worker process.

With `use_process=True`, sends shutdown to the worker; if it does not exit, terminates the process, then shuts down the manager.

With `use_process=False`, attempts `local()` before closing the SCPI connection.

### disconnect()

Alias for `close()`.

### get_state()

Returns the current state as a dictionary.

With `use_process=True`, adds `process_alive` to the shared state.

With `use_process=False`, adds `process_alive=False` to the direct-mode state.

The main keys are:

```python
{
    "worker_alive": True,
    "process_alive": True,
    "port": "/dev/cu.usbserial-10",
    "baudrate": 115200,
    "running": False,
    "job_id": None,
    "job_type": None,
    "started_at": None,
    "finished_at": None,
    "error": None,
    "traceback": None,
    "message": "worker_ready",
    "args": {},
    "mode": "voltage_dc",
    "range_value": 10,
    "auto_range": False,
    "integration_speed": "F",
    "continue_interval": 0.1,
    "continue_duration": 10.0,
    "continue_count": None,
}
```

`args` stores the arguments received by the worker while a job is running.

### is_running()

Returns `True` during a long-running measurement.

### wait_until_done(poll_interval=0.2)

Waits until `running` becomes `False`. Returns a dictionary equivalent to `get_state()` at completion.

Args:

```python
poll_interval: float = 0.2
```

Returns:

```python
state: dict
```

## Instrument Identification API

### idn()

Returns the response to `*IDN?`.

Unavailable while running; calling it then raises `DeviceBusyError`.

Returns:

```python
"OWON,..."
```

## Configuration API

### set_mode(mode)

Sets the measurement mode for both single and continuous measurements.

Args:

```python
mode: str
```

Supported `mode` values are:

```text
voltage_dc
voltage_ac
current_dc
current_ac
resistance
fresistance
frequency
period
capacitance
temperature_rtd
diode
continuity
```

The following mapping is used to set the SCPI `FUNCtion`:

```text
voltage_dc      -> VOLT
voltage_ac      -> VOLT AC
current_dc      -> CURR
current_ac      -> CURR AC
resistance      -> RES
fresistance     -> FRES
frequency       -> FREQ
period          -> PER
capacitance     -> CAP
temperature_rtd -> TEMP
diode           -> DIOD
continuity      -> CONT
```

Calling `set_mode()` invalidates the cached `range_value` and `auto_range`, since the range depends on the measurement mode.

Returns:

```python
{"mode": mode}
```

### set_range(value=None, index=None, range_value=None)

Sets a manual range for the current measurement mode, for both single and continuous measurements.

Args:

```python
value: str | int | float | None
index: int | None
range_value: str | int | float | None
```

`value` specifies a physical quantity. Numeric values are interpreted in the base unit of the current measurement mode.

```text
voltage_dc, voltage_ac       -> V
current_dc, current_ac       -> A
resistance, fresistance      -> Ohm
capacitance                  -> F
temperature_rtd              -> KITS90 or PT100
```

Unit-bearing strings are accepted with or without spaces.

```python
dmm.set_mode("voltage_dc")
dmm.set_range(value=5.0)        # 5 V range
dmm.set_range(value="500 mV")  # 500 mV range
dmm.set_range(value="500mV")   # 500 mV range
```

`index` directly specifies a discrete SCPI `RANGE` index from the XDM1000 Programming Manual.

```python
dmm.set_mode("voltage_dc")
dmm.set_range(index=3)          # DCV 5 V range
```

Do not specify `value`, `index`, and `range_value` together. `range_value` is a legacy-compatible alias for `value`.

The ctrl layer checks the requested value against the current mode and converts only supported discrete ranges to SCPI `RANGE <index>`. Afterward, the `auto_range` cache is set to `False`.

`set_mode()` is required before `set_range()`.

Returns:

```python
{
    "range_value": value | None,
    "range_index": index,
    "range_label": "5 V",
}
```

### set_auto_range(enabled)

Sets auto-ranging for both single and continuous measurements.

Args:

```python
enabled: bool
```

When `enabled=True`, the SCPI layer issues `AUTO`.

When `enabled=False`, the XDM1000 SCPI interface is not sent a generic `AUTO OFF`. Instead, the most recent `range_index` determined by `set_range()` is re-applied using `RANGE <index>`. Therefore, call `set_range()` before setting `enabled=False`.

`set_mode()` is required before `set_auto_range()`.

Returns:

```python
{"auto_range": True | False}
```

### set_integration_speed(speed)

Sets the internal measurement speed for both single and continuous measurements.

Args:

```python
speed: str
```

The following values are accepted; lowercase input is converted to uppercase.

```text
F: high speed
M: middle speed
S: low speed
```

The SCPI command is named `RATE`, but the ctrl API calls this `integration_speed` to avoid confusion with the interval between measurement samples. The continuous-measurement interval is set by `set_continue_interval()`.

Returns:

```python
{"integration_speed": speed}
```

## Continuous-Measurement Settings API

### set_continue_interval(interval)

Sets the interval between measurement starts during continuous measurement.

Args:

```python
interval: float
```

The unit is seconds. The value must be nonnegative; `0.0` reads as quickly as possible.

The implementation treats it as the minimum interval from the start of one sample to the target start time of the next.

Returns:

```python
{"continue_interval": interval}
```

### set_continue_duration(duration)

Sets the maximum duration of continuous measurement.

Args:

```python
duration: float | None
```

The unit is seconds. `None` disables the time limit; a numeric `duration` must be positive.

If both `duration` and `continue_count` are configured, measurement ends when the first limit is reached.

Returns:

```python
{"continue_duration": duration}
```

### set_continue_count(count)

Sets the maximum number of continuous-measurement samples.

Args:

```python
count: int | None
```

`None` disables the sample-count limit; a numeric `count` must be a positive integer.

If both `duration` and `count` are `None`, `meas_continue()` raises `ValueError`.

Returns:

```python
{"continue_count": count}
```

## Measurement API

### meas(wait=None)

Takes one measurement using the current settings.

Args:

```python
wait: float | None = None
```

`wait` is not an SCPI feature. It is a Python-side delay, in seconds, immediately before measurement. `None` means no delay.

`mode`, `range_value`, and `integration_speed` are not measurement-call arguments. Set them beforehand using the configuration API.

`set_mode()` is required before `meas()`.

Returns:

```python
{
    "type": "single",
    "mode": "voltage_dc",
    "range_value": 10,
    "auto_range": False,
    "integration_speed": "F",
    "value": 1.234,
    "host_time_start": 1710000000.0,
    "host_time_end": 1710000000.02,
    "read_elapsed": 0.02,
}
```

The returned result is stored for subsequent retrieval using `get_result()`.

### meas_continue(wait=None)

Starts or executes continuous measurement using the current settings.

Args:

```python
wait: float | None = None
```

`wait` is not an SCPI feature. It is a Python-side delay, in seconds, before continuous measurement starts. `None` means no delay.

At minimum, configure the following before calling `meas_continue()`:

```python
dmm.set_mode("voltage_dc")
dmm.set_continue_duration(10.0)
```

Alternatively:

```python
dmm.set_mode("voltage_dc")
dmm.set_continue_count(100)
```

Returns:

```python
{"job_id": "..."}
```

With `use_process=True`, the worker process continues measuring and only the job ID is returned to the caller. Retrieve the result with `get_result()`.

With `use_process=False`, the measurement loop runs in the calling process, and the job ID is returned after completion. The call therefore blocks until measurement finishes.

## Result Retrieval API

### get_result(clear=False)

Returns the most recent single- or continuous-measurement result.

Args:

```python
clear: bool = False
```

With `clear=True`, the stored result is removed after retrieval.

A single-measurement result has `type="single"`; a continuous-measurement result has `type="continuous"`.

Example single-measurement result:

```python
{
    "type": "single",
    "mode": "voltage_dc",
    "range_value": 10,
    "auto_range": False,
    "integration_speed": "F",
    "value": 1.234,
    "host_time_start": 1710000000.0,
    "host_time_end": 1710000000.02,
    "read_elapsed": 0.02,
}
```

Example continuous-measurement result:

```python
{
    "type": "continuous",
    "job_id": "...",
    "ok": True,
    "mode": "voltage_dc",
    "range_value": 10,
    "auto_range": False,
    "integration_speed": "F",
    "continue_interval": 0.1,
    "continue_duration": 10.0,
    "continue_count": None,
    "stats": {
        "count": 100,
        "minimum": 1.23,
        "maximum": 1.25,
        "average": 1.24,
        "stdev_population": 0.01
    },
    "started_at": 1710000000.0,
    "finished_at": 1710000010.0,
    "samples": [
        {
            "index": 0,
            "value": 1.234,
            "host_time_start": 1710000000.0,
            "host_time_end": 1710000000.02,
            "read_elapsed": 0.02,
            "t_rel_start": 0.0,
            "t_rel_end": 0.02
        }
    ]
}
```

In the current direct implementation (`use_process=False`), continuous results omit `stats`, `started_at`, and `finished_at` and include `count` instead.

## Restrictions While Running

The following APIs cannot be called during a running measurement:

```text
idn()
set_mode()
set_range()
set_auto_range()
set_integration_speed()
set_continue_interval()
set_continue_duration()
set_continue_count()
meas()
meas_continue()
```

Calling one of them while running raises `DeviceBusyError`.

The following APIs can still be called while running:

```text
get_state()
is_running()
get_result()
wait_until_done()
```

## Transparent FastAPI

The APIs exposed by `server_fastapi/spec.py` are:

```text
get_state
is_running
idn
set_mode
set_range
set_auto_range
set_integration_speed
set_continue_interval
set_continue_duration
set_continue_count
meas
meas_continue
get_result
wait_until_done
```

Each API is registered with `object_name="xdm1000"` and HTTP method `post`.

The request models are:

```text
set_mode                  -> ModeRequest(mode: str)
set_range                 -> RangeRequest(value: str | int | float | None, index: int | None, range_value: str | int | float | None)
set_auto_range            -> AutoRangeRequest(enabled: bool)
set_integration_speed     -> IntegrationSpeedRequest(speed: str)
set_continue_interval     -> ContinueIntervalRequest(interval: float)
set_continue_duration     -> ContinueDurationRequest(duration: float | None)
set_continue_count        -> ContinueCountRequest(count: int | None)
meas                      -> WaitRequest(wait: float | None)
meas_continue             -> WaitRequest(wait: float | None)
get_result                -> ClearRequest(clear: bool = False)
wait_until_done           -> WaitUntilDoneRequest(poll_interval: float = 0.2)
```

## Minimal Usage Examples

### Single Measurement

```python
from xdm1000.xdm1000_ctrl import Xdm1000Ctrl

dmm = Xdm1000Ctrl(port="/dev/cu.usbserial-10")

try:
    dmm.set_mode("voltage_dc")
    dmm.set_auto_range(True)
    dmm.set_integration_speed("F")
    result = dmm.meas()
    print(result)
finally:
    dmm.close()
```

### Continuous Measurement

```python
from xdm1000.xdm1000_ctrl import Xdm1000Ctrl

dmm = Xdm1000Ctrl(port="/dev/cu.usbserial-10")

try:
    dmm.set_mode("voltage_dc")
    dmm.set_auto_range(True)
    dmm.set_integration_speed("F")
    dmm.set_continue_interval(0.1)
    dmm.set_continue_duration(10.0)

    job = dmm.meas_continue()
    print(job)

    dmm.wait_until_done()
    result = dmm.get_result()
    print(result)
finally:
    dmm.close()
```
