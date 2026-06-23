# 上位制御層 (xdm1000_ctrl.py)

`xdm1000_ctrl.py` は、XDM1000/XDM1241 を測定器として扱う上位制御クラスを提供する。SCPI 低レベル API をそのまま公開する層ではない。

## 公開される主な API

```text
close()
disconnect()
get_state()
is_running()
stop_job()
get_continuous_result(clear=False)
get_statistics_result(clear=False)
idn()
set_meas_mode(kind, range_value="AUTO", rate="F")
meas_one_shot(kind=None, range_value=None, rate=None, settle=0.0)
meas(kind=None, range_value=None, rate=None, settle=0.0)
meas_voltage_dc(range_value=None, rate=None, settle=0.0)
meas_current_dc(range_value=None, rate=None, settle=0.0)
start_continuous_meas(kind=None, duration=0.0, range_value=None, rate=None, interval=0.0, settle=0.0)
start_statistics_mode(kind=None, duration=0.0, range_value=None, rate=None, settle=0.0)
wait_until_done(poll_interval=0.2)
```

`remote()`、`local()`、`query()`、`write()` は公開しない。

## use_process=True

`use_process=True` では、親プロセスが API を受け、子プロセスである worker が SCPI 通信を担当する。

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

## use_process=False

`use_process=False` では、`Xdm1000Ctrl` 自身が `Xdm1000Scpi` を生成する。`start_continuous_meas()` と `start_statistics_mode()` は同じ API 名だが、バックグラウンド化されず、呼び出し元でブロッキング実行される。

## running 中の制約

`idn()`、`set_meas_mode()`、`meas_one_shot()`、`meas()`、`meas_voltage_dc()`、`meas_current_dc()`、`start_continuous_meas()`、`start_statistics_mode()` は running 中に実行できない。running 中に呼ぶと `DeviceBusyError` が送出される。

`get_state()`、`is_running()`、`stop_job()`、`get_continuous_result()`、`get_statistics_result()` は running 中でも呼べる。

## state

`get_state()` は現在状態を dict として返す。`use_process=True` では共有 dict に `process_alive` を追加して返す。`use_process=False` では direct 用状態に `process_alive=False` を追加して返す。

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
```

## stop

`stop_job()` は command queue を使わない。`use_process=True` では `stop_event` を set する。`use_process=False` では direct 用の停止要求フラグを立てる。実際の停止は測定ループが次に停止要求を確認した時点で行われる。

## continuous 測定

`start_continuous_meas()` は `duration` 秒の間 `MEAS1?` を繰り返す。`interval` が 0 より大きい場合は、サンプル間の最低間隔として扱う。`duration <= 0` または `interval < 0` は `ValueError` である。

`use_process=True` では開始成功時に `{"job_id": ...}` を返し、結果は `result_store["continuous"]` に保存される。

## statistics mode

`start_statistics_mode()` は `duration` 秒の統計測定を行う。`duration <= 0` は `ValueError` である。

`use_process=True` では、worker が `CALCulate:FUNCtion AVERage` を設定し、指定時間中に `MEAS1?` を読みつつ、最後に `CALCulate:AVERage:ALL?` を取得して `stats` に保存する。

`use_process=False` では、Python 側で `MEAS1?` の値列から `minimum`、`maximum`、`average`、`count` を計算する。

## 結果取得

`get_continuous_result(clear=False)` と `get_statistics_result(clear=False)` は保存済み結果を返す。`clear=True` の場合、取得後に該当結果を消す。
