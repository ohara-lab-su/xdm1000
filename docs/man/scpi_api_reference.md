# SCPI ドライバ API リファレンス

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

### meas_raw()

```text
MEAS?
```

の生応答を返す。

---

### meas()

```text
MEAS?
```

の応答を float または tuple として返す。
戻り値の構造は装置の表示状態に依存する可能性がある。
したがって ctrl 層の標準測定 API では使用しない。

---

### meas_main()

```text
MEAS1?
```

メイン表示値を float として返す。
ctrl 層の 1shot / continuous ではこれを使用する。

---

### meas_sub()

```text
MEAS2?
```

サブ表示値を float として返す。
ctrl 層の基本 API では使用しない。
