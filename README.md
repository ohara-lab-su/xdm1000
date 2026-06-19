# xdm1000 FastAPI server module

OWON XDM1000/XDM1241 用の `ese774_frame` 透過サーバー構成である。

## 構成

``` text
project_root/
├── src/
│   └── xdm1000/
│       ├── xdm1000_ctrl.py
│       └── server_fastapi/
│           ├── spec.py
│           ├── make.py
│           ├── models/
│           ├── routers/
│           └── clients/
└── examples/
    ├── serve_xdm1000.py
    └── measure_xdm1000.py
```

`xdm1000_ctrl.py` はローカル制御クラスであり、ローカル利用では直接使う。
サーバー利用では同じ制御クラスを `FastApiServer` の `device_cls`
として渡し、`server_fastapi/spec.py` で公開 API を選別する。

## .pyi 生成

``` bash
python -m xdm1000.server_fastapi.make
```

## サーバー起動

``` bash
python examples/serve_xdm1000.py
```

## 測定サンプル

``` bash
python examples/measure_xdm1000.py
```

# SCPI ドライバ層 (`xdm1000_scpi.py`)

`xdm1000_scpi.py` は OWON XDM1000 シリーズの SCPI コマンドをほぼ 1 対 1
に対応付ける低レベルドライバである。SCPI
の抽象化は最小限とし、装置マニュアルのコマンド体系をそのまま Python API
に反映することを目的とする。

## 主な機能

-   IEEE488.2
    -   `idn()`
    -   `reset()`
-   System
    -   `remote()`
    -   `local()`
    -   `set_beeper()`
    -   `get_beeper()`
-   Configure
    -   DC/AC 電圧
    -   DC/AC 電流
    -   2 線抵抗
    -   4 線抵抗
    -   周波数
    -   周期
    -   容量
    -   RTD 温度
    -   ダイオード
    -   導通
-   Sense
    -   測定機能選択
    -   レンジ
    -   AUTO/MANUAL
    -   Rate(F/S/M)
    -   温度設定
    -   NULL
    -   dB / dBm
-   Measure
    -   `measure()`
    -   `measure_main()`
    -   `measure_sub()`

本クラスは SCPI ドライバであり、測定シーケンスの管理は行わない。

## 測定速度

OWON の仕様では積分時間(NPLC)ではなく `Rate` を使用する。

-   Fast
-   Medium
-   Slow

Fast は高速更新、Slow
はノイズ性能を優先する。詳細な更新速度・確度はユーザーマニュアルおよび
Programming Manual に従う。

------------------------------------------------------------------------

# xdm1000 FastAPI server module

OWON XDM1000/XDM1241 用の制御ライブラリ、および `ese774_frame` 透過サーバー構成である。

本ファイルは統合版 README の Part 1 である。

- `xdm1000_scpi.py`
  - SCPI を低レベル API として提供する。
  - SCPI コマンドは削らない。
  - `remote()` / `local()` はこの層のみ。

- `xdm1000_ctrl.py`
  - 測定器として扱う上位制御層。
  - SCPI を隠蔽する。
  - `remote()` / `local()` は公開しない。

## 構成

```text
project_root/
├── src/
│   └── xdm1000/
│       ├── xdm1000_scpi.py
│       ├── xdm1000_ctrl.py
│       └── server_fastapi/
└── examples/
```

## 設計目的

- ローカル制御クラスとして設計する。
- FastAPI や ese774_frame には依存しない。
- サーバープロセスで実体化されることを前提とする。
- 長時間測定は multiprocessing.Process を使用する。
- 測定中は running 状態を保持する。

## SCPI 採用方針

SCPI ドライバ層では、Programming Manual に記載されている SCPI コマンドを可能な限りそのまま公開する。

上位制御層では、SCPI の存在を利用者に意識させない API を提供する。

上位層では測定器として自然な API を提供することを目的とし、SCPI コマンド体系は隠蔽する。

SCPI は削らない。

上位層で現在利用しない SCPI コマンドであっても、低レベル API として実装する。

---

### CONFigure

CONFigure 系コマンドは測定モードの切り替えを行う。

代表例

- CONFigure:VOLTage:DC
- CONFigure:VOLTage:AC
- CONFigure:CURRent:DC
- CONFigure:CURRent:AC
- CONFigure:RESistance
- CONFigure:FRESistance
- CONFigure:FREQuency
- CONFigure:PERiod
- CONFigure:CAPacitance
- CONFigure:TEMPerature:RTD
- CONFigure:DIODe
- CONFigure:CONTinuity

SCPI 層では個別メソッドとして提供する。

ctrl 層では

```python
set_measurement_mode(
    kind="voltage_dc",
    range_value="AUTO",
    rate="F",
)
```

へ集約する。

---

### SENSe

SENSe 系では測定条件を設定する。

代表的なものは

- Rate
- Range
- Auto Range
- Null
- dB
- dBm

である。

Rate は

- F
- M
- S

の3段階であり、
これは装置内部の測定速度であって、
continuous 測定で指定する polling interval とは意味が異なる。

---

## MEAS 系コマンド

Programming Manual では測定値取得として少なくとも次が提供される。

```
MEAS?
MEAS1?
MEAS2?
```

これらは用途が異なる。

---

### MEAS?

汎用測定値取得コマンドである。
現在の表示状態に応じた測定値を返す。
表示モードによって戻り値の構造が変わる可能性があるため、
ctrl 層では標準 API として採用しない。
SCPI 層では

```python
measure()
```

として公開する。

---

### MEAS1?

メイン表示値取得である。
ctrl 層では
主測定値
として採用する。
理由

- 常に単一値として扱える
- API の戻り値を固定できる
- continuous 測定を単純な時系列として保存できる

1shot
continuous
ともに MEAS1? を使用する。

---

### MEAS2?

サブ表示取得である。

SCPI 層では

```python
measure_sub()
```

として提供する。
ctrl 層では現在は公開しない。
サブ表示の意味は測定モードに依存するため、
将来必要になった段階で専用 API として設計する。

---

## CALCulate

CALCulate は測定コマンドではなく、
測定値に対する演算機能である。

代表例

- CALCulate:FUNCtion
- CALCulate:AVERage:MINimum?
- CALCulate:AVERage:MAXimum?
- CALCulate:AVERage:AVERage?
- CALCulate:AVERage:ALL?

CALCulate:AVERage:ALL? は

- minimum
- maximum
- average
- count

を返す。

これは時間指定平均ではない。
Statistics 機能である。
Statistics の開始条件・終了条件・リセット条件については Programming Manual の記述だけでは仕様が確定できないため、
ctrl 層では
Statistics Mode
というテスト機能として実装する。
時間窓平均としては扱わない。

---

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

# プロセスモデル

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
        measure_one_shot()
start_continuous_measurement()
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
- set_measurement_mode
- measure_one_shot
- start_continuous_measurement
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
measurement_mode
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

# running の扱い

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

- measure_one_shot()
- set_measurement_mode()
- start_continuous_measurement()
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

# 状態遷移

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

# 測定モード

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

# SCPI ドライバ API

`xdm1000_scpi.py` は低レベル API として提供する。

この層は
測定器が持つ SCPI コマンドを
なるべくそのまま公開する。
上位制御層で使用しない API であっても削らない。

---

## 基本通信

### open()

シリアルポートを開く。
既に開いている場合は何もしない。

---

### close()

シリアルポートを閉じる。

---

### write(command)

SCPI コマンドを送信する。
戻り値を読まない。

例

```python
dmm.write("SYSTem:REMote")
```

---

### query(command)

SCPI クエリを送信し、文字列応答を返す。

例

```python
text = dmm.query("*IDN?")
```

---

### query_float(command)

SCPI クエリ応答を float として返す。

---

### query_int(command)

SCPI クエリ応答を int として返す。

---

### query_bool(command)

SCPI クエリ応答を bool として返す。

---

## IEEE 488.2

### idn()

```text
*IDN?
```

装置識別文字列を返す。

---

### reset()

```text
*RST
```

装置をリセットする。

---

## System

### remote()

```text
SYSTem:REMote
```

装置を remote 状態にする。

この API は SCPI ドライバ層にのみ存在する。

ctrl 層には公開しない。

---

### local()

```text
SYSTem:LOCal
```

装置を local 状態に戻す。

この API は SCPI ドライバ層にのみ存在する。

ctrl 層には公開しない。

---

### set_beeper(enabled)

ブザー設定を行う。

---

### get_beeper()

ブザー設定を取得する。

---

## Sense / Configure

### set_function(function)

測定機能を設定する。

SCPI の機能名をそのまま渡す低レベル API である。

---

### get_function()

現在の測定機能を取得する。

---

### set_main_function(function)

メイン表示側の測定機能を設定する。

---

### get_main_function()

メイン表示側の測定機能を取得する。

---

### set_sub_function(function)

サブ表示側の測定機能を設定する。

---

### get_sub_function()

サブ表示側の測定機能を取得する。

---

### set_range(value)

レンジを設定する。

---

### get_range()

レンジ設定を取得する。

---

### auto()

オートレンジを設定する。

---

### get_auto()

オートレンジ状態を取得する。

---

### set_rate(rate)

測定速度を設定する。

`rate` は

```text
F
M
S
```

を指定する。

---

### get_rate()

測定速度設定を取得する。

---

### configure_voltage_dc(range_value="AUTO")

DC 電圧測定に設定する。

---

### configure_voltage_ac(range_value="AUTO")

AC 電圧測定に設定する。

---

### configure_current_dc(range_value="AUTO")

DC 電流測定に設定する。

---

### configure_current_ac(range_value="AUTO")

AC 電流測定に設定する。

---

### configure_resistance(range_value="AUTO")

2線抵抗測定に設定する。

---

### configure_fresistance(range_value="AUTO")

4線抵抗測定に設定する。

---

### configure_frequency(range_value="AUTO")

周波数測定に設定する。

---

### configure_period(range_value="AUTO")

周期測定に設定する。

---

### configure_capacitance(range_value="AUTO")

容量測定に設定する。

---

### configure_temperature_rtd(rtd_type=None)

RTD 温度測定に設定する。

---

### configure_diode()

ダイオード測定に設定する。

---

### configure_continuity()

導通測定に設定する。

---

## Temperature / Continuity

### set_temperature_rtd_type(rtd_type)

RTD 種別を設定する。

---

### get_temperature_rtd_type()

RTD 種別を取得する。

---

### set_temperature_unit(unit)

温度単位を設定する。

---

### get_temperature_unit()

温度単位を取得する。

---

### set_temperature_show(show)

温度表示形式を設定する。

---

### get_temperature_show()

温度表示形式を取得する。

---

### set_continuity_threshold(resistance_ohm)

導通しきい値を設定する。

---

### get_continuity_threshold()

導通しきい値を取得する。

---

## CALCulate

### set_calc_state(enabled)

CALCulate 機能の ON/OFF を設定する。

---

### calc_off()

CALCulate 機能を OFF にする。

---

### set_calc_function(function)

CALCulate の機能を設定する。

例

```text
AVERage
NULL
DB
DBM
```

---

### get_calc_function()

現在の CALCulate 機能を取得する。

---

### get_average_all_raw()

```text
CALCulate:AVERage:ALL?
```

の生応答を返す。

---

### get_average_all()

```text
CALCulate:AVERage:ALL?
```

の応答を構造化して返す。

戻り値は概念的に次を含む。

```text
minimum
maximum
average
count
```

---

### get_average()

statistics の平均値を取得する。

---

### get_average_maximum()

statistics の最大値を取得する。

---

### get_average_minimum()

statistics の最小値を取得する。

---

### set_db_reference(value)

dB 基準値を設定する。

---

### get_db_reference()

dB 基準値を取得する。

---

### set_dbm_reference(value)

dBm 基準抵抗を設定する。

---

### get_dbm_reference()

dBm 基準抵抗を取得する。

---

### set_null_offset(value)

NULL オフセットを設定する。

---

### get_null_offset()

NULL オフセットを取得する。

---

## Measure

### measure_raw()

```text
MEAS?
```

の生応答を返す。

---

### measure()

```text
MEAS?
```

の応答を float または tuple として返す。
戻り値の構造は装置の表示状態に依存する可能性がある。
したがって ctrl 層の標準測定 API では使用しない。

---

### measure_main()

```text
MEAS1?
```

メイン表示値を float として返す。
ctrl 層の 1shot / continuous ではこれを使用する。

---

### measure_sub()

```text
MEAS2?
```

サブ表示値を float として返す。
ctrl 層の基本 API では使用しない。
