[![en](https://img.shields.io/badge/lang-en-red.svg)](https://ohara-lab-su.github.io/xdm1000/en/manual/ctrl_api_reference.html) [![ja](https://img.shields.io/badge/lang-ja-blue.svg)](https://ohara-lab-su.github.io/xdm1000/ja/manual/ctrl_api_reference.html)

# ctrl API リファレンス

`xdm1000_ctrl.py` は XDM1000 / XDM1241 を測定器として扱う利用者向け上位制御 API を提供する。SCPI 層は SCPI コマンドの薄いラッパであり、ctrl 層では測定モード、レンジ、オートレンジ、内部測定速度、連続測定条件を上位 API として整理する。

本書は現在の `xdm1000_ctrl.py`、`xdm1000_worker.py`、`server_fastapi/spec.py` に合わせた API リファレンスである。

## 設計方針

測定条件は `meas()` / `meas_continue()` の引数に混ぜない。測定前に `set_mode()`、`set_range()`、`set_auto_range()`、`set_integration_speed()` で測定器状態を設定する。

単発測定と連続測定は、測定入口で分ける。

```python
result = dmm.meas()
job = dmm.meas_continue()
```

連続測定だけに必要な周期・終了条件は、`set_continue_interval()`、`set_continue_duration()`、`set_continue_count()` で設定する。

## 公開 API

現在の `Xdm1000Ctrl` が利用者向けに持つ主な API は以下である。

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

以下の旧 API は現在の `Xdm1000Ctrl` には存在しない。

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

`remote()`、`local()`、`query()`、`write()` は ctrl API として公開しない。これらは SCPI 層の責務である。

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

`use_process=False` では同一プロセス内で `Xdm1000Ctrl` 自身が SCPI オブジェクトを直接持つ。

## 状態・ライフサイクル

### close()

接続または worker process を閉じる。

`use_process=True` では worker に shutdown を送り、終了しない場合は process を terminate する。その後、manager を shutdown する。

`use_process=False` では `local()` を試みた後、SCPI 接続を close する。

### disconnect()

`close()` の別名である。

### get_state()

現在状態を dict として返す。

`use_process=True` では共有 state に `process_alive` を追加して返す。

`use_process=False` では direct 用状態に `process_alive=False` を追加して返す。

主なキーは以下である。

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

`args` は running 中の worker が受け取った引数を保持する。

### is_running()

長時間測定中なら True を返す。

### wait_until_done(poll_interval=0.2)

`running` が False になるまで待つ。戻り値は終了時点の `get_state()` 相当の dict である。

Args:

```python
poll_interval: float = 0.2
```

Returns:

```python
state: dict
```

## 装置識別 API

### idn()

`*IDN?` の応答を返す。

running 中は実行できない。running 中に呼ぶと `DeviceBusyError` である。

Returns:

```python
"OWON,..."
```

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

SCPI 側では、次の対応で `FUNCtion` を設定する。

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

`set_mode()` を呼ぶと、以前の `range_value` と `auto_range` のキャッシュは無効化される。レンジは測定モードに依存するためである。

Returns:

```python
{"mode": mode}
```

### set_range(value=None, index=None, range_value=None)

現在の測定モードに対する手動レンジを設定する。単発測定と連続測定で共通である。

Args:

```python
value: str | int | float | None
index: int | None
range_value: str | int | float | None
```

`value` は物理量指定である。数値で指定した場合、単位は現在の測定モードの基本単位である。

```text
voltage_dc, voltage_ac       -> V
current_dc, current_ac       -> A
resistance, fresistance      -> Ohm
capacitance                  -> F
temperature_rtd              -> KITS90 または PT100
```

単位付き文字列は、空白あり・空白なしの両方を受け付ける。

```python
dmm.set_mode("voltage_dc")
dmm.set_range(value=5.0)        # 5 V レンジ
dmm.set_range(value="500 mV")  # 500 mV レンジ
dmm.set_range(value="500mV")   # 500 mV レンジ
```

`index` は XDM1000 Programming Manual の SCPI `RANGE` 離散番号を直接指定する。

```python
dmm.set_mode("voltage_dc")
dmm.set_range(index=3)          # DCV 5 V レンジ
```

`value`、`index`、`range_value` は同時に指定しない。`range_value` は旧 API 互換用であり、`value` と同じ意味で扱う。

ctrl 層は現在の測定モードと指定値を照合し、許可された離散レンジだけを SCPI `RANGE <index>` へ変換する。呼び出し後、`auto_range` キャッシュは False になる。

`set_range()` の前に `set_mode()` が必要である。

Returns:

```python
{
    "range_value": value | None,
    "range_index": index,
    "range_label": "5 V",
}
```

### set_auto_range(enabled)

オートレンジを設定する。単発測定と連続測定で共通である。

Args:

```python
enabled: bool
```

`enabled=True` の場合、SCPI 側では `AUTO` を発行する。

`enabled=False` の場合、XDM1000 の SCPI には汎用の `AUTO OFF` を送らず、直近の `set_range()` で決定した `range_index` を `RANGE <index>` で再設定する。したがって `enabled=False` にするには、先に `set_range()` が必要である。

`set_auto_range()` の前に `set_mode()` が必要である。

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

指定値は以下である。小文字を渡した場合も大文字化して扱う。

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

実装上は、各サンプルの測定開始時刻から次の測定開始目標時刻までの最低間隔として扱う。

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

単位は秒である。`None` で時間制限を無効化する。`duration` に数値を指定する場合は正の値でなければならない。

`duration` と `continue_count` が両方設定されている場合は、先に到達した条件で終了する。

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

`None` で回数制限を無効化する。`count` に数値を指定する場合は正の整数でなければならない。

`duration` と `count` が両方 None の場合、`meas_continue()` は `ValueError` である。

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

`meas()` の前に `set_mode()` が必要である。

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

現在設定で連続測定を開始または実行する。

Args:

```python
wait: float | None = None
```

`wait` は SCPI 機能ではない。Python 側で連続測定開始前に待つ秒数である。`None` の場合は待たない。

`meas_continue()` の前に、少なくとも以下を設定する必要がある。

```python
dmm.set_mode("voltage_dc")
dmm.set_continue_duration(10.0)
```

または

```python
dmm.set_mode("voltage_dc")
dmm.set_continue_count(100)
```

Returns:

```python
{"job_id": "..."}
```

`use_process=True` では worker process が測定を継続し、呼び出し元には job_id だけ返る。結果は `get_result()` で取得する。

`use_process=False` では同一プロセス内で測定ループを実行し、終了後に job_id を返す。したがって呼び出しは連続測定終了までブロックする。

## 結果取得 API

### get_result(clear=False)

直近の単発測定または連続測定結果を返す。

Args:

```python
clear: bool = False
```

`clear=True` の場合は、取得後に保存結果を消す。

単発測定後の結果は `type="single"` である。連続測定後の結果は `type="continuous"` である。

単発測定結果例:

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

`use_process=False` の連続測定結果では、現在の direct 実装上、`stats`、`started_at`、`finished_at` は含まれず、代わりに `count` が含まれる。

## running 中の制約

次の API は running 中に実行できない。

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

running 中に呼ぶと `DeviceBusyError` が送出される。

次の API は running 中でも呼べる。

```text
get_state()
is_running()
get_result()
wait_until_done()
```

## FastAPI 透過 API

`server_fastapi/spec.py` で公開される API は以下である。

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

各 API は `object_name="xdm1000"` として登録され、HTTP method は `post` である。

request model は以下である。

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

## 最小使用例

### 単発測定

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

### 連続測定

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
