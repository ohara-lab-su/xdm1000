# XDM1000 / XDM1241 測定仕様と ctrl API 対応

本書は、XDM1000 / XDM1241 で測定時に選択できるパラメータと、`xdm1000_ctrl.py` での指定方法をまとめる。

## 基本 API

| 操作 | ctrl API | 備考 |
|---|---|---|
| 測定モード選択 | `set_mode(mode)` | 電圧、電流、抵抗などを選択する。 |
| オートレンジ | `set_auto_range(True)` | 装置側のオートレンジを使用する。 |
| 手動レンジ指定 | `set_range(value)` | 物理量または単位付き文字列で指定する。 |
| SCPIレンジ番号指定 | `set_range_index(index)` | マニュアルの離散番号を直接指定する。通常は使用しない。 |
| 測定速度指定 | `set_integration_speed(speed)` | `"F"`, `"M"`, `"S"` を指定する。 |
| 1点測定 | `meas()` | 現在設定で測定値を取得する。 |
| 連続測定 | `meas_continue()` | 現在設定で連続測定する。 |

## レンジ指定の扱い

`set_range(value)` は測定モードに応じて、指定値を SCPI の `RANGE` 離散番号へ変換する。

例: `voltage_dc` で `set_range("5 V")` または `set_range(5.0)` を指定すると、内部では `RANGE 3` を送信する。

SCPI の離散番号を直接指定する場合は `set_range_index(index)` を使う。

## 測定モード

| 測定対象 | ctrl mode | 手動レンジ |
|---|---|---|
| DC電圧 | `"voltage_dc"` | 対応 |
| AC電圧 | `"voltage_ac"` | 対応 |
| DC電流 | `"current_dc"` | 対応 |
| AC電流 | `"current_ac"` | 対応 |
| 2端子抵抗 | `"resistance"` | 対応 |
| 4端子抵抗 | `"fresistance"` | 対応 |
| 周波数 | `"frequency"` | 手動レンジなし |
| 周期 | `"period"` | 手動レンジなし |
| 静電容量 | `"capacitance"` | 対応 |
| 温度 | `"temperature_rtd"` | センサ種別を選択 |
| ダイオード | `"diode"` | 手動レンジなし |
| 導通 | `"continuity"` | 手動レンジなし |

## DC電圧

ctrl mode: `"voltage_dc"`  
数値指定の単位: V

| レンジ | `set_range(value)` | `set_range_index(index)` |
|---:|---|---:|
| 50 mV | `0.05`, `"50 mV"` | `1` |
| 500 mV | `0.5`, `"500 mV"` | `2` |
| 5 V | `5.0`, `"5 V"` | `3` |
| 50 V | `50.0`, `"50 V"` | `4` |
| 500 V | `500.0`, `"500 V"` | `5` |
| 1000 V | `1000.0`, `"1000 V"` | `6` |

## AC電圧

ctrl mode: `"voltage_ac"`  
数値指定の単位: V

| レンジ | `set_range(value)` | `set_range_index(index)` |
|---:|---|---:|
| 500 mV | `0.5`, `"500 mV"` | `1` |
| 5 V | `5.0`, `"5 V"` | `2` |
| 50 V | `50.0`, `"50 V"` | `3` |
| 500 V | `500.0`, `"500 V"` | `4` |
| 750 V | `750.0`, `"750 V"` | `5` |

## DC電流

ctrl mode: `"current_dc"`  
数値指定の単位: A

| レンジ | `set_range(value)` | `set_range_index(index)` |
|---:|---|---:|
| 500 μA | `0.0005`, `"500 uA"` | `1` |
| 5 mA | `0.005`, `"5 mA"` | `2` |
| 50 mA | `0.05`, `"50 mA"` | `3` |
| 500 mA | `0.5`, `"500 mA"` | `4` |
| 5 A | `5.0`, `"5 A"` | `5` |
| 10 A | `10.0`, `"10 A"` | `6` |

## AC電流

ctrl mode: `"current_ac"`  
数値指定の単位: A

| レンジ | `set_range(value)` | `set_range_index(index)` |
|---:|---|---:|
| 500 μA | `0.0005`, `"500 uA"` | `1` |
| 5 mA | `0.005`, `"5 mA"` | `2` |
| 50 mA | `0.05`, `"50 mA"` | `3` |
| 500 mA | `0.5`, `"500 mA"` | `4` |
| 5 A | `5.0`, `"5 A"` | `5` |
| 10 A | `10.0`, `"10 A"` | `6` |

## 抵抗

ctrl mode: `"resistance"`, `"fresistance"`  
数値指定の単位: Ω

| レンジ | `set_range(value)` | `set_range_index(index)` |
|---:|---|---:|
| 500 Ω | `500.0`, `"500 Ohm"` | `1` |
| 5 kΩ | `5000.0`, `"5 kOhm"` | `2` |
| 50 kΩ | `50000.0`, `"50 kOhm"` | `3` |
| 500 kΩ | `500000.0`, `"500 kOhm"` | `4` |
| 5 MΩ | `5000000.0`, `"5 MOhm"` | `5` |
| 50 MΩ | `50000000.0`, `"50 MOhm"` | `6` |

## 静電容量

ctrl mode: `"capacitance"`  
数値指定の単位: F

| レンジ | `set_range(value)` | `set_range_index(index)` |
|---:|---|---:|
| 50 nF | `50e-9`, `"50 nF"` | `1` |
| 500 nF | `500e-9`, `"500 nF"` | `2` |
| 5 μF | `5e-6`, `"5 uF"` | `3` |
| 50 μF | `50e-6`, `"50 uF"` | `4` |
| 500 μF | `500e-6`, `"500 uF"` | `5` |
| 5 mF | `5e-3`, `"5 mF"` | `6` |
| 50 mF | `50e-3`, `"50 mF"` | `7` |

## 温度

ctrl mode: `"temperature_rtd"`

| センサ | `set_range(value)` | `set_range_index(index)` |
|---|---|---:|
| KITS90 | `"KITS90"` | `1` |
| PT100 | `"PT100"` | `2` |

## 測定速度

ctrl API: `set_integration_speed(speed)`

| 指定値 | 装置側設定 | 測定速度 | 1回の測定時間目安 | 用途 |
|---|---|---:|---:|---|
| `"F"` | High speed | 65 readings/s | 約15.4 ms | 高速変化の監視 |
| `"M"` | Middle speed | 16 readings/s | 約62.5 ms | 通常のPython測定 |
| `"S"` | Low speed | 4 readings/s | 約250 ms | 安定値取得、ノイズ低減 |

測定速度は装置内部の更新速度である。Python からのSCPI取得周期を保証しない。

## 使用例

DC電圧、5 Vレンジ、Middle speed:

```python
dmm.set_mode("voltage_dc")
dmm.set_range("5 V")
dmm.set_integration_speed("M")
value = dmm.meas()
```

DC電流、5 mAレンジ、Middle speed:

```python
dmm.set_mode("current_dc")
dmm.set_range("5 mA")
dmm.set_integration_speed("M")
value = dmm.meas()
```

抵抗、50 kΩレンジ:

```python
dmm.set_mode("resistance")
dmm.set_range("50 kOhm")
value = dmm.meas()
```

SCPIレンジ番号を直接指定する場合:

```python
dmm.set_mode("voltage_dc")
dmm.set_range_index(3)
value = dmm.meas()
```
