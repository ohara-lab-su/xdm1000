# ctrl API リファレンス

`xdm1000_ctrl.py` は利用者向けの上位制御 API を提供する。SCPI 層は SCPI コマンドの薄いラッパであり、ctrl 層では測定器の設定値をキャッシュし、単発測定と連続測定の入口だけを分ける。

## 設計方針

測定条件は `meas()` / `meas_continue()` の引数に混ぜない。測定前に `set_mode()`、`set_range()`、`set_auto_range()`、`set_integration_speed()` で測定器状態を設定する。

単発測定と連続測定は、測定入口で分ける。

```python
value = dmm.meas()
job = dmm.meas_continue()
```

連続測定だけに必要な周期・終了条件は、`set_continue_interval()`、`set_continue_duration()`、`set_continue_count()` で設定する。

## Xdm1000Ctrl 初期化

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

`config` がある場合は `PORT`、`TIMEOUT`、`BAUDRATE` を優先する。最終的に `port` がない場合は `ValueError` である。

`use_process=True` では worker process が実体の SCPI オブジェクトを持つ。親プロセス側は worker に命令を送り、共有 state / result store から状態と結果を読む。

`use_process=False` では同一プロセス内で SCPI オブジェクトを直接持つ。

## 状態・ライフサイクル

### close()

接続または worker process を閉じる。

### disconnect()

`close()` の別名である。

### get_state()

現在状態を dict として返す。

主なキーは以下である。

```python
{
    "worker_alive": True,
    "process_alive": True,
    "running": False,
    "job_id": None,
    "job_type": None,
    "mode": "voltage_dc",
    "range_value": 10,
    "auto_range": False,
    "integration_speed": "F",
    "continue_interval": 0.1,
    "continue_duration": 10.0,
    "continue_count": None,
    "error": None,
    "traceback": None,
}
```

### is_running()

連続測定中なら True を返す。

### wait_until_done(poll_interval=0.2)

`running` が False になるまで待つ。

## 設定 API

### set_mode(mode)

測定モードを設定する。単発測定と連続測定で共通である。

Args:

```python
mode: str
```

利用可能な `mode` は以下である。

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

SCPI 側では `FUNCtion "..."` を発行する。

`set_mode()` を呼ぶと、以前の `range_value` と `auto_range` のキャッシュは無効化される。レンジは測定モードに依存するためである。

Returns:

```python
{"mode": mode}
```

### set_range(range_value)

現在の測定モードに対する手動レンジを設定する。単発測定と連続測定で共通である。

Args:

```python
range_value: str | int | float
```

例:

```python
dmm.set_range(10)
dmm.set_range("DEF")
```

SCPI 側では `RANGE <range_value>` を発行する。呼び出し後、`auto_range` キャッシュは False になる。

Returns:

```python
{"range_value": range_value}
```

### set_auto_range(enabled)

オートレンジを設定する。単発測定と連続測定で共通である。

Args:

```python
enabled: bool
```

`enabled=True` の場合、SCPI 側では `AUTO` を発行する。

`enabled=False` の場合、XDM1000 の SCPI には汎用の `AUTO OFF` を送らず、直近の `set_range()` で保持している手動レンジを `RANGE <range_value>` で再設定する。したがって `enabled=False` にするには、先に `set_range()` が必要である。

Returns:

```python
{"auto_range": True | False}
```

### set_integration_speed(speed)

内部測定速度を設定する。単発測定と連続測定で共通である。

Args:

```python
speed: str
```

指定値は以下である。

```text
F: high speed
M: middle speed
S: low speed
```

SCPI コマンド名は `RATE` だが、ctrl API では測定点間隔と誤解しないように `integration_speed` と呼ぶ。これは連続測定の周期ではない。連続測定の周期は `set_continue_interval()` で設定する。

Returns:

```python
{"integration_speed": speed}
```

## 連続測定条件 API

### set_continue_interval(interval)

連続測定時の測定開始間隔を設定する。

Args:

```python
interval: float
```

単位は秒である。0 以上の値を指定する。`0.0` の場合は可能な限り連続して読む。

Returns:

```python
{"continue_interval": interval}
```

### set_continue_duration(duration)

連続測定の最大測定時間を設定する。

Args:

```python
duration: float | None
```

単位は秒である。`None` で時間制限を無効化する。`duration` と `continue_count` が両方設定されている場合は、先に到達した条件で終了する。

Returns:

```python
{"continue_duration": duration}
```

### set_continue_count(count)

連続測定の最大測定回数を設定する。

Args:

```python
count: int | None
```

`None` で回数制限を無効化する。`duration` と `count` が両方 None の場合、`meas_continue()` は `ValueError` である。

Returns:

```python
{"continue_count": count}
```

## 測定 API

### meas(wait=None)

現在設定で 1 回測定する。

Args:

```python
wait: float | None = None
```

`wait` は SCPI 機能ではない。Python 側で測定直前に待つ秒数である。`None` の場合は待たない。

`mode`、`range_value`、`integration_speed` は引数に持たせない。必要なら測定前に設定 API を呼ぶ。

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

戻り値は `get_result()` でも取得できるように保存される。

### meas_continue(wait=None)

現在設定で連続測定を開始する。

Args:

```python
wait: float | None = None
```

`wait` は SCPI 機能ではない。Python 側で連続測定開始前に待つ秒数である。`None` の場合は待たない。

`meas_continue()` の前に、`set_continue_duration()` または `set_continue_count()` の少なくとも一方を設定する必要がある。

Returns:

```python
{"job_id": "..."}
```

`use_process=True` では worker process が測定を継続し、呼び出し元には job_id だけ返る。結果は `get_result()` で取得する。

`use_process=False` では同一プロセス内で測定ループを実行し、終了後に job_id を返す。

## 結果取得 API

### get_result(clear=False)

直近の単発測定または連続測定結果を返す。

Args:

```python
clear: bool = False
```

`clear=True` の場合は、取得後に保存結果を消す。

単発測定後の結果は `type="single"` である。連続測定後の結果は `type="continuous"` である。

連続測定結果例:

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
