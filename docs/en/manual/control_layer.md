[![en](https://img.shields.io/badge/lang-en-red.svg)](https://ohara-lab-su.github.io/xdm1000/en/manual/control_layer.html) [![ja](https://img.shields.io/badge/lang-ja-blue.svg)](https://ohara-lab-su.github.io/xdm1000/ja/manual/control_layer.html)

# High-Level Control Layer

`Xdm1000Ctrl` is the instrument-oriented API. It manages measurement mode, range, integration speed, continuous-measurement settings, cached state and results. With `use_process=True`, a child worker owns the serial connection; the parent uses queues and shared state. With `use_process=False`, SCPI executes in the caller process. The source document explicitly distinguishes the current `set_mode` / `meas_continue` interface from older APIs.

> **Documentation scope:** This English guide is an abridged technical companion to the complete Japanese manual. This page is a summary of the supplied Japanese document; consult the Japanese version for details and complete examples.

## Responsibilities

### SCPI

```text
serial.Serial を開く
SCPI コマンドを write/query する
*IDN? を問い合わせる
FUNCtion / RANGE / RATE / MEAS1? などを薄く包む
```

### ctrl

```text
測定モード名を ctrl API 名として整理する
測定モード、レンジ、オートレンジ、内部測定速度を保持する
単発測定と連続測定の入口を分ける
連続測定条件を保持する
process 分離時の worker との RPC を管理する
測定結果を result store に保存する
```

### worker

```text
親プロセスから command queue で指示を受ける
SCPI オブジェクトを保持する
測定器状態を共有 state に反映する
単発測定結果および連続測定結果を result store に保存する
```

## SCPI layer

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

## Control layer

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

## Worker layer

## Public API

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

## Process mode

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

## Direct mode

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

## Initialization

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

## State

```python
dmm.set_mode("voltage_dc")
dmm.set_range(value=5.0)
dmm.set_range(value="500 mV")
dmm.set_range(value="500mV")
```

```python
dmm.set_range(index=3)
```

## Restrictions during acquisition

```text
F
M
S
```

## Measurement modes

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

## Manual range

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

## Integration speed

## Single measurement

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
