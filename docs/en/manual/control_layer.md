# High-Level Control Layer (xdm1000_ctrl.py)

`xdm1000_ctrl.py` provides a high-level control class for operating the XDM1000 / XDM1241 as measurement instruments. It does not simply expose the low-level SCPI API.

The current control layer requires the instrument state to be configured explicitly before calling `meas()` or `meas_continue()`. The ctrl layer caches the measurement mode, range, internal measurement speed, and continuous-measurement settings, and reflects them in shared state on the worker-process side.

## Separation of Responsibilities

### SCPI Layer

`xdm1000_scpi.py` is a low-level SCPI wrapper.

Its main responsibilities are:

```text
Open serial.Serial
Write/query SCPI commands
Query *IDN?
Provide thin wrappers for FUNCtion / RANGE / RATE / MEAS1?, etc.
```

### ctrl Layer

`xdm1000_ctrl.py` provides the user-facing API.

Its main responsibilities are:

```text
Map measurement modes to ctrl API names
Maintain mode, range, auto-ranging, and internal measurement speed
Provide separate entry points for single and continuous measurements
Maintain continuous-measurement settings
Manage RPC to the worker in process-separated mode
Store measurement results in the result store
```

### Worker Layer

When `use_process=True`, `xdm1000_worker.py` holds the SCPI instance in a child process.

Its main responsibilities are:

```text
Receive commands from the parent via the command queue
Own the SCPI object
Reflect instrument status in shared state
Store single- and continuous-measurement results in the result store
```

## Main Public APIs

The main public APIs of the current `Xdm1000Ctrl` are:

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

The following are legacy APIs and are not present in the current `Xdm1000Ctrl`:

```text
stop_job()
get_continuous_result(clear=False)
get_statistics_result(clear=False)
set_meas_mode(kind, range_value="AUTO", rate="F")
meas_one_shot(kind=None, range_value=None, rate=None, settle=0.0)
meas_voltage_dc(range_value=None, rate=None, settle=0.0)
meas_current_dc(range_value=None, rate=None, settle=0.0)
start_continuous_meas(kind=None, duration=0.0, range_value=None, rate=None, interval=0.0, settle=0.0)
start_statistics_mode(kind=None, duration=0.0, range_value=None, rate=None, settle=0.0)
```

`remote()`, `local()`, `query()`, and `write()` are not exposed. They belong to the SCPI layer.

## use_process=True

With `use_process=True`, the parent process receives user API calls, while the child worker process handles SCPI communication.

```text
Xdm1000Ctrl
├── Parent Process
│   ├── command_q
│   ├── response_q
│   ├── Manager().dict() state
│   ├── Manager().dict() result_store
│   ├── Event stop_event
│   └── Lock rpc_lock
└── Worker Process
    └── _Xdm1000Worker
        └── Xdm1000Scpi
            └── serial.Serial
```

Only the worker process owns the serial port. The parent process does not execute SCPI operations directly.

The parent-side `meas_continue()` sends a start request to the worker and returns after receiving `{"job_id": "..."}`. The measurement loop continues in the worker, and results are retrieved using `get_result()`.

## use_process=False

With `use_process=False`, `Xdm1000Ctrl` creates its own `Xdm1000Scpi` instance. SCPI commands execute directly in the same process.

Although the API name is still `meas_continue()`, the call runs synchronously and blocks the caller. After completion, it returns `{"job_id": "..."}`.

## Initialization

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

When `config` is supplied, its `PORT`, `TIMEOUT`, and `BAUDRATE` values take precedence. A missing final `port` raises `ValueError`.

With `use_process=True`, initialization creates `mp.Manager()`, command and response queues, a stop event, an RPC lock, and a worker process.

With `use_process=False`, initialization creates `Xdm1000Scpi` and calls `remote()`.

## state

`get_state()` returns the current state as a dictionary.

With `use_process=True`, `process_alive` is added to the shared dictionary. With `use_process=False`, `process_alive=False` is added to the direct-mode state.

The principal keys are:

```text
worker_alive
process_alive
port
baudrate
running
job_id
job_type
started_at
finished_at
error
traceback
message
args
mode
range_value
auto_range
integration_speed
continue_interval
continue_duration
continue_count
```

`mode`, `range_value`, `auto_range`, `integration_speed`, `continue_interval`, `continue_duration`, and `continue_count` are configuration values cached by the ctrl layer.

## Restrictions While Running

The following APIs cannot be called while a measurement is running:

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

Calling them while running raises `DeviceBusyError`.

The following APIs remain available while running:

```text
get_state()
is_running()
get_result()
wait_until_done()
```

The current implementation does not provide `stop_job()`. Continuous measurement stops when `continue_duration` or `continue_count` is reached.

## Measurement Modes

The ctrl API mode names map to SCPI `FUNCtion` parameters as follows:

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

An unsupported mode raises `ValueError`.


## Manual Range

`set_range(value=None, index=None, range_value=None)` selects a manual range for the current measurement mode.

`value` specifies a physical quantity. A numeric value uses the base unit of the current mode: V for voltage, A for current, Ohm for resistance, and F for capacitance.

```python
dmm.set_mode("voltage_dc")
dmm.set_range(value=5.0)
dmm.set_range(value="500 mV")
dmm.set_range(value="500mV")
```

`index` directly selects a discrete SCPI `RANGE` index.

```python
dmm.set_range(index=3)
```

Do not specify `value`, `index`, and `range_value` together. `range_value` is a legacy-compatible alias for `value`.

## Internal Measurement Speed

`set_integration_speed(speed)` sets the SCPI `RATE`.

Accepted values are:

```text
F
M
S
```

Lowercase input is converted to uppercase. Other values raise `ValueError`.

`integration_speed` is the instrument’s internal measurement speed, not the sample interval of a continuous measurement. Use `set_continue_interval()` to set that interval.

## Single Measurement

`meas(wait=None)` reads `MEAS1?` once using the current settings.

`set_mode()` must be called before `meas()`.

The result can also be retrieved with `get_result()`.

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

## Continuous Measurement

`meas_continue(wait=None)` performs continuous measurement using the current settings.

At least one of `set_continue_duration()` and `set_continue_count()` must be configured before `meas_continue()`. If both values are `None`, it raises `ValueError`.

The `interval` argument of `set_continue_interval(interval)` must be nonnegative. With zero, samples are read as quickly as possible.

The `duration` argument of `set_continue_duration(duration)` must be `None` or positive.

The `count` argument of `set_continue_count(count)` must be `None` or a positive integer.

With `use_process=True`, a successful start returns `{"job_id": ...}` and the result is stored in `result_store["result"]`.

A continuous-measurement result has the following form:

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

In direct mode (`use_process=False`), the continuous result does not include `stats`; it includes `count` instead.

## Retrieving Results

`get_result(clear=False)` returns the most recent single- or continuous-measurement result.

With `clear=True`, the stored result is deleted after retrieval.

`get_continuous_result()` and `get_statistics_result()` are not current APIs. Use `get_result()` for all results.

## Transparent FastAPI

The transparent APIs exposed by `server_fastapi/spec.py` are:

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

All use `object_name="xdm1000"` and HTTP method `post`.
