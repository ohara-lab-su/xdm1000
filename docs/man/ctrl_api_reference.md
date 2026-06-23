# ctrl API リファレンス

`xdm1000_ctrl.py` は上位制御 API を提供する。SCPI ドライバの全 API を公開するものではない。

## 例外

### DeviceBusyError

running 中に、同時実行できない測定・設定 API が呼ばれた場合に送出される。

### DeviceWorkerError

worker process 側で発生した例外を親プロセス側へ伝播するために送出される。

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

## ライフサイクル

### close()

`use_process=True` では worker へ `shutdown` を送り、終了しない場合は terminate する。その後 manager を shutdown する。`use_process=False` では `local()` を試行し、シリアルポートを閉じる。

### disconnect()

`close()` の別名である。

## 状態取得

### get_state()

現在状態を dict として返す。`use_process=True` では共有 state に `process_alive` を加える。`use_process=False` では direct state に `process_alive=False` を加える。

### is_running()

running 中なら True を返す。

### wait_until_done(poll_interval=0.2)

`get_state()` を繰り返し、`running` が False になるまで待つ。現状の実装ではループごとに `STATE:` を標準出力へ出す。

## 停止

### stop_job()

長時間測定に停止要求を出す。戻り値は要求直後の state である。

`use_process=True` では `stop_event.set()` を行う。`use_process=False` では direct 停止フラグを立てる。

## 結果取得

### get_continuous_result(clear=False)

保存済み continuous 結果を返す。存在しない場合は None である。`clear=True` の場合は取得後に保存結果を削除または None にする。

`use_process=True` の結果例:

```python
{
    "job_id": "...",
    "ok": True,
    "stopped": False,
    "kind": "voltage_dc",
    "range_value": "AUTO",
    "rate": "F",
    "duration_requested": 10.0,
    "stats": {
        "count": 100,
        "minimum": 1.23,
        "maximum": 1.25,
        "average": 1.24,
        "stdev_population": 0.01,
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
            "t_rel_end": 0.02,
        }
    ],
}
```

### get_statistics_result(clear=False)

保存済み statistics 結果を返す。存在しない場合は None である。`clear=True` の場合は取得後に保存結果を削除または None にする。

`use_process=True` の結果例:

```python
{
    "job_id": "...",
    "ok": True,
    "stopped": False,
    "kind": "voltage_dc",
    "range_value": "AUTO",
    "rate": "F",
    "duration_requested": 10.0,
    "stats": {
        "minimum": 1.23,
        "maximum": 1.25,
        "average": 1.24,
        "count": 120,
    },
    "note": "CALCulate:AVERage:ALL? を使った statistics テスト結果である。...",
    "started_at": 1710000000.0,
    "finished_at": 1710000010.0,
    "values": [1.23, 1.24],
}
```

## 通常 API

### idn()

`*IDN?` の結果を返す。running 中は実行できない。

### set_meas_mode(kind, range_value="AUTO", rate="F")

測定種別、レンジ、レートを設定する。戻り値は次の dict である。

```python
{
    "kind": kind,
    "range_value": range_value,
    "rate": rate,
}
```

利用可能な `kind` は次である。

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

### meas_one_shot(kind=None, range_value=None, rate=None, settle=0.0)

1回だけ測定する。省略された `kind`、`range_value`、`rate` は現在キャッシュまたは既定値で補完される。

戻り値は dict である。

```python
{
    "kind": "voltage_dc",
    "range_value": "AUTO",
    "rate": "F",
    "value": 1.234,
    "host_time_start": 1710000000.0,
    "host_time_end": 1710000000.02,
    "read_elapsed": 0.02,
}
```

### meas(kind=None, range_value=None, rate=None, settle=0.0)

`meas_one_shot()` の短縮名である。戻り値も `meas_one_shot()` と同じ dict である。

### meas_voltage_dc(range_value=None, rate=None, settle=0.0)

`kind="voltage_dc"` で `meas_one_shot()` を呼ぶ。

### meas_current_dc(range_value=None, rate=None, settle=0.0)

`kind="current_dc"` で `meas_one_shot()` を呼ぶ。

## 長時間測定 API

### start_continuous_meas(kind=None, duration=0.0, range_value=None, rate=None, interval=0.0, settle=0.0)

疑似 continuous 測定を開始する。`duration <= 0.0` または `interval < 0.0` は `ValueError` である。

戻り値は次である。

```python
{"job_id": "..."}
```

`use_process=True` では開始成功時に戻り、測定は worker process で継続する。結果は `get_continuous_result()` で取得する。

`use_process=False` では呼び出し元で測定ループを実行し、終了後に戻る。

### start_statistics_mode(kind=None, duration=0.0, range_value=None, rate=None, settle=0.0)

statistics mode のテスト測定を開始する。`duration <= 0.0` は `ValueError` である。

戻り値は次である。

```python
{"job_id": "..."}
```

`use_process=True` では `CALCulate:AVERage:ALL?` の結果を保存する。`use_process=False` では Python 側で値列から統計を計算する。
