[![en](https://img.shields.io/badge/lang-en-red.svg)](https://ohara-lab-su.github.io/xdm1000/en/manual/control_layer.html) [![ja](https://img.shields.io/badge/lang-ja-blue.svg)](https://ohara-lab-su.github.io/xdm1000/ja/manual/control_layer.html)

# 上位制御層 (xdm1000_ctrl.py)

`xdm1000_ctrl.py` は、XDM1000 / XDM1241 を測定器として扱う上位制御クラスを提供する。SCPI 低レベル API をそのまま公開する層ではない。

現在の上位制御層は、測定器状態を明示的に設定してから `meas()` または `meas_continue()` を呼ぶ構成である。測定モード、レンジ、内部測定速度、連続測定条件は ctrl 層がキャッシュし、worker process 側にも共有 state として反映する。

## 責務分離

### SCPI 層

`xdm1000_scpi.py` は低レベル SCPI ラッパである。

主な責務は以下である。

```text
serial.Serial を開く
SCPI コマンドを write/query する
*IDN? を問い合わせる
FUNCtion / RANGE / RATE / MEAS1? などを薄く包む
```

### ctrl 層

`xdm1000_ctrl.py` は利用者向け API を提供する。

主な責務は以下である。

```text
測定モード名を ctrl API 名として整理する
測定モード、レンジ、オートレンジ、内部測定速度を保持する
単発測定と連続測定の入口を分ける
連続測定条件を保持する
process 分離時の worker との RPC を管理する
測定結果を result store に保存する
```

### worker 層

`xdm1000_worker.py` は `use_process=True` のとき、子プロセス側で SCPI 実体を保持する。

主な責務は以下である。

```text
親プロセスから command queue で指示を受ける
SCPI オブジェクトを保持する
測定器状態を共有 state に反映する
単発測定結果および連続測定結果を result store に保存する
```

## 公開される主な API

現在の `Xdm1000Ctrl` の主な公開 API は以下である。

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

以下は旧 API であり、現在の `Xdm1000Ctrl` には存在しない。

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

`remote()`、`local()`、`query()`、`write()` は公開しない。これらは SCPI 層の API である。

## use_process=True

`use_process=True` では、親プロセスが利用者 API を受け、子プロセスである worker が SCPI 通信を担当する。

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

worker process のみがシリアルポートを保持する。親プロセスは SCPI を直接実行しない。

親プロセス側の `meas_continue()` は worker に開始要求を送り、`{"job_id": "..."}` を受け取って戻る。測定ループは worker 側で継続する。結果は `get_result()` で取得する。

## use_process=False

`use_process=False` では、`Xdm1000Ctrl` 自身が `Xdm1000Scpi` を生成する。SCPI は同一プロセス内で直接実行される。

`meas_continue()` は同じ API 名だが、バックグラウンド化されず、呼び出し元でブロッキング実行される。終了後、戻り値として `{"job_id": "..."}` を返す。

## 初期化

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

`use_process=True` の場合、初期化時に `mp.Manager()`、command queue、response queue、stop event、RPC lock、worker process を生成する。

`use_process=False` の場合、初期化時に `Xdm1000Scpi` を生成し、`remote()` を実行する。

## state

`get_state()` は現在状態を dict として返す。

`use_process=True` では共有 dict に `process_alive` を追加して返す。`use_process=False` では direct 用状態に `process_alive=False` を追加して返す。

主なキーは次である。

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

`mode`、`range_value`、`auto_range`、`integration_speed`、`continue_interval`、`continue_duration`、`continue_count` は ctrl 層が保持する設定キャッシュである。

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

現在の実装には `stop_job()` はない。連続測定は `continue_duration` または `continue_count` に到達すると終了する。

## 測定モード

ctrl API の測定モード名と SCPI `FUNCtion` パラメータの対応は以下である。

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

未対応の mode を指定すると `ValueError` である。


## 手動レンジ

`set_range(value=None, index=None, range_value=None)` は、現在の測定モードに対する手動レンジを設定する。

`value` は物理量指定である。数値で指定した場合、単位は現在の測定モードの基本単位である。電圧系は V、電流系は A、抵抗系は Ohm、静電容量は F である。

```python
dmm.set_mode("voltage_dc")
dmm.set_range(value=5.0)
dmm.set_range(value="500 mV")
dmm.set_range(value="500mV")
```

`index` は SCPI `RANGE` 離散番号を直接指定する。

```python
dmm.set_range(index=3)
```

`value`、`index`、`range_value` は同時に指定しない。`range_value` は旧 API 互換用であり、`value` と同じ意味で扱う。

## 内部測定速度

`set_integration_speed(speed)` は SCPI `RATE` を設定する。

指定値は以下である。

```text
F
M
S
```

小文字を渡した場合も大文字化して扱う。これ以外の値は `ValueError` である。

`integration_speed` は測定器内部の測定速度である。連続測定のサンプル間隔ではない。連続測定のサンプル間隔は `set_continue_interval()` で設定する。

## 単発測定

`meas(wait=None)` は現在設定で 1 回 `MEAS1?` を読む。

`meas()` の前に `set_mode()` が必要である。

結果は `get_result()` で再取得できる。

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

## continuous 測定

`meas_continue(wait=None)` は現在設定で連続測定を行う。

`meas_continue()` の前に `set_continue_duration()` または `set_continue_count()` の少なくとも一方を設定する必要がある。両方が None の場合は `ValueError` である。

`set_continue_interval(interval)` の `interval` は 0 以上でなければならない。0 の場合は可能な限り連続して読む。

`set_continue_duration(duration)` の `duration` は None または正の値である。

`set_continue_count(count)` の `count` は None または正の整数である。

`use_process=True` では開始成功時に `{"job_id": ...}` を返し、結果は `result_store["result"]` に保存される。

連続測定結果は以下の形式である。

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

`use_process=False` の direct 実装では、連続測定結果に `stats` は付与されず、`count` が付与される。

## 結果取得

`get_result(clear=False)` は直近の単発測定または連続測定結果を返す。

`clear=True` の場合、取得後に保存結果を消す。

`get_continuous_result()` と `get_statistics_result()` は現在の API ではない。結果取得は `get_result()` に統一する。

## FastAPI 透過 API

`server_fastapi/spec.py` で公開される透過 API は以下である。

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

`object_name` はすべて `xdm1000` であり、HTTP method は `post` である。
