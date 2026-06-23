# 上位制御層 (xdm1000_ctrl.py)

上位制御層は
SCPI のラッパ
ではない。

測定器として自然な API を提供することを目的とする。
利用者は
MEAS1?
CONFigure
SENSe
CALCulate
などを意識しない。

---

## 責務

ctrl 層が担当するもの

- 測定モード設定
- 1shot 測定
- continuous 測定
- statistics mode
- running 管理
- state 管理
- result 管理
- stop
- close

担当しないもの

- raw SCPI
- remote/local
- query()

これらは SCPI 層だけが提供する。

## プロセスモデル

この部分が `xdm1000_ctrl.py` の中核となる設計である。
本ライブラリでは Python の `threading` は使用しない。
長時間測定は `multiprocessing.Process` を使用する。
理由は次の通りである。

- Python スレッドは GIL の影響を受ける。
- 長時間 Blocking I/O を安全に分離したい。
- 測定処理を API ハンドラから完全に独立させたい。
- 将来 FastAPI・gRPC・ローカル利用のいずれでも同一設計を維持したい。

---

## 全体構成

```text
                   ctrl API
        meas_one_shot()
start_continuous_meas()
 start_statistics_mode()
           │
           ▼
     Parent Process
──────────────────────────────

running
state
result
command queue
response queue
stop event
           │
           ▼
──────────────────────────────
      Worker Process
    XDM1000SCPI
    Serial Port
    SCPI Execute
```

worker process のみがシリアルポートを保持する。
親プロセスはシリアルポートへ直接アクセスしない。

---

## Parent Process

親プロセスは API を公開する側である。

責務

- API 呼び出し受付
- running 管理
- state 管理
- result 管理
- command queue 管理
- response queue 管理
- stop event 管理

親プロセスは

```text
query()
write()
MEAS?
```

などの SCPI を直接実行しない。

---

## Worker Process

Worker Process は
SCPI を実行する唯一のプロセスである。

責務

- XDM1000SCPI の生成
- open()
- close()
- シリアル保持
- SCPI 実行
- 測定実行
- statistics 実行
- continuous 実行
- result 保存
- state 更新

---

## command queue

```text
Parent Process
↓
Worker Process
```

へ命令を送る。

対象

- idn
- reset
- set_meas_mode
- meas_one_shot
- start_continuous_meas
- start_statistics_mode
- shutdown

command queue は
短時間コマンド
だけを対象とする。

---

## response queue

```text
Worker Process
↓
Parent Process
```

へ応答を返す。

通常コマンドでは

```text
command queue
↓
Worker
↓
response queue
```

という流れになる。

---

## state

state は共有状態である。
少なくとも次を保持する。

```text
running
job_type
job_id
meas_mode
range
rate
started_time
finished_time
sample_count
last_value
message
error
```

state は queue を経由せず取得できる。
そのため

```
get_state()
```

は長時間測定中でも即座に返る。

---

## result

測定終了後の結果を保存する。

```text
continuous
statistics
```

それぞれ専用の結果を保持する。
Parent Process は
測定終了後に

```
get_result()
```

で取得する。

---

## stop event

停止要求は
command queue
では行わない。
Parent Process が

```
stop_event.set()
```

を行う。
Worker Process は
測定ループ中に
一定周期で

```
stop_event.is_set()
```

を確認する。
停止要求があれば
安全に測定を終了する。

---

## running の扱い

running は
長時間ジョブ実行中かどうか
を示す。

running=True の間は
測定器は占有状態である。

---

## running 中に許可する API

- get_state()
- is_running()
- stop_job()
- get_result()

これらは

Worker Process を停止させない。

---

## running 中に禁止する API

- meas_one_shot()
- set_meas_mode()
- start_continuous_meas()
- start_statistics_mode()
- reset()

これらは

command queue に積まない。

Parent Process が

```
DeviceBusyError
```

を返す。
これにより
Worker Process は
測定処理だけに集中できる。

---

## 状態遷移

```text
Idle
↓
Running
↓
Finished

```

正常終了時は
Finished
になる。

---

```text
Idle
↓
Running
↓
Stopped

```

stop_job()
により停止した場合は
Stopped
となる。

---

```text
Idle
↓
Running
↓
Error

```

例外が発生した場合は
Error
になる。
Error 時には
error メッセージを state に保持する。

---

## 測定モード

ctrl 層では
測定モードを
次の3種類に限定する。

---

## one shot

1回だけ測定する。

使用する SCPI

```
CONFigure
SENSe
MEAS1?
```

戻り値

```text
value
host_time_start
host_time_end
elapsed
```

---

## continuous

指定時間
MEAS1?
を繰り返し取得する。
各サンプルは

```text
index
value
host_time_start
host_time_end
elapsed
```

を保持する。
測定終了後
まとめて取得する。

---

## statistics

SCPI の

```
CALCulate
```

機能を利用する。
現在は
Statistics 機能の評価用であり
時間平均 API としては扱わない。
使用する SCPI

```
CALCulate:FUNCtion
CALCulate:AVERage:ALL?
```

戻り値

```
minimum
maximum
average
count
```

である。
