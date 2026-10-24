[![en](https://img.shields.io/badge/lang-en-red.svg)](https://ohara-lab-su.github.io/xdm1000/en/manual/ctrl_api_reference.html) [![ja](https://img.shields.io/badge/lang-ja-blue.svg)](https://ohara-lab-su.github.io/xdm1000/ja/manual/ctrl_api_reference.html)

# Control API Reference

This is the instrument-oriented API reference. Configure mode, range, autoranging, and integration speed before invoking `meas()` or `meas_continue()`. Continuous acquisition has separate interval, duration and count settings. `get_result()` retrieves results; `get_state()` reports controller status. The Japanese source explicitly marks several earlier convenience methods as obsolete.

> **Documentation scope:** This English guide is an abridged technical companion to the complete Japanese manual. This page is a summary of the supplied Japanese document; consult the Japanese version for details and complete examples.

## Design principles

```python
result = dmm.meas()
job = dmm.meas_continue()
```

## Public API

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

## Controller initialization

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

## State and lifecycle

### close()

### disconnect()

### get_state()

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

### is_running()

### wait_until_done(poll_interval=0.2)

```python
poll_interval: float = 0.2
```

```python
state: dict
```

## Close

### idn()

```python
"OWON,..."
```

## Disconnect

### set_mode(mode)

```python
mode: str
```

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

```python
{"mode": mode}
```

### set_range(value=None, index=None, range_value=None)

```python
value: str | int | float | None
index: int | None
range_value: str | int | float | None
```

```text
voltage_dc, voltage_ac       -> V
current_dc, current_ac       -> A
resistance, fresistance      -> Ohm
capacitance                  -> F
temperature_rtd              -> KITS90 または PT100
```

```python
dmm.set_mode("voltage_dc")
dmm.set_range(value=5.0)        # 5 V レンジ
dmm.set_range(value="500 mV")  # 500 mV レンジ
dmm.set_range(value="500mV")   # 500 mV レンジ
```

```python
dmm.set_mode("voltage_dc")
dmm.set_range(index=3)          # DCV 5 V レンジ
```

```python
{
    "range_value": value | None,
    "range_index": index,
    "range_label": "5 V",
}
```

### set_auto_range(enabled)

```python
enabled: bool
```

```python
{"auto_range": True | False}
```

### set_integration_speed(speed)

```python
speed: str
```

```text
F: high speed
M: middle speed
S: low speed
```

```python
{"integration_speed": speed}
```

## Get state

### set_continue_interval(interval)

```python
interval: float
```

```python
{"continue_interval": interval}
```

### set_continue_duration(duration)

```python
duration: float | None
```

```python
{"continue_duration": duration}
```

### set_continue_count(count)

```python
count: int | None
```

```python
{"continue_count": count}
```

## Check running

### meas(wait=None)

```python
wait: float | None = None
```

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

### meas_continue(wait=None)

```python
wait: float | None = None
```

```python
dmm.set_mode("voltage_dc")
dmm.set_continue_duration(10.0)
```

```python
dmm.set_mode("voltage_dc")
dmm.set_continue_count(100)
```

```python
{"job_id": "..."}
```

## Wait until complete

### get_result(clear=False)

```python
clear: bool = False
```

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

## Instrument identification

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

```text
get_state()
is_running()
get_result()
wait_until_done()
```

## Identify instrument

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

## Configuration API

### Details 12

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

### Details 12

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
