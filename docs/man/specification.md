# XDM1241 測定仕様と ctrl API 対応

本書は XDM1241 で測定時に選択できる主要パラメータと、`Xdm1000Ctrl` から指定する API を対応させた一覧である。

## 基本手順

```python
dmm.set_mode("voltage_dc")
dmm.set_auto_range(True)
dmm.set_integration_speed("M")
value = dmm.meas()
```

手動レンジを使う場合は、`set_auto_range(True)` の代わりに `set_range()` を使う。

```python
dmm.set_mode("voltage_dc")
dmm.set_range(value=5.0)
dmm.set_integration_speed("M")
value = dmm.meas()
```

## 測定モード

| 測定対象 | ctrl API | SCPI function |
|---|---|---|
| DC 電圧 | `set_mode("voltage_dc")` | `VOLT` |
| AC 電圧 | `set_mode("voltage_ac")` | `VOLT AC` |
| DC 電流 | `set_mode("current_dc")` | `CURR` |
| AC 電流 | `set_mode("current_ac")` | `CURR AC` |
| 2 線抵抗 | `set_mode("resistance")` | `RES` |
| 4 線抵抗 | `set_mode("fresistance")` | `FRES` |
| 周波数 | `set_mode("frequency")` | `FREQ` |
| 周期 | `set_mode("period")` | `PER` |
| 静電容量 | `set_mode("capacitance")` | `CAP` |
| 温度 | `set_mode("temperature_rtd")` | `TEMP` |
| ダイオード | `set_mode("diode")` | `DIOD` |
| 導通 | `set_mode("continuity")` | `CONT` |

## レンジ指定 API

手動レンジは `set_range(value=None, index=None, range_value=None)` で指定する。

| 指定方法 | 意味 |
|---|---|
| `set_range(value=5.0)` | 物理量で指定する。電圧系では V 単位である。 |
| `set_range(value="500 mV")` | 単位付き文字列で指定する。 |
| `set_range(value="500mV")` | 空白なしの単位付き文字列で指定する。 |
| `set_range(index=3)` | SCPI `RANGE` 離散番号を直接指定する。 |

`value` と `index` は同時に指定しない。`range_value` は旧 API 互換用であり、`value` と同じ意味である。

数値 `value` の基本単位は測定モードで決まる。

| 測定モード | 数値 `value` の単位 |
|---|---|
| `voltage_dc`, `voltage_ac` | V |
| `current_dc`, `current_ac` | A |
| `resistance`, `fresistance` | Ohm |
| `capacitance` | F |
| `temperature_rtd` | 文字列のみ |

ctrl 層は `value` をモード別の離散レンジ表で検証し、SCPI 層へは `RANGE <index>` を渡す。

## DC 電圧レンジ

`set_mode("voltage_dc")` 後に指定する。

| ハードウェアレンジ | `set_range(value=...)` | `set_range(index=...)` |
|---|---:|---:|
| 50 mV | `0.05` または `"50 mV"` / `"50mV"` | `1` |
| 500 mV | `0.5` または `"500 mV"` / `"500mV"` | `2` |
| 5 V | `5.0` または `"5 V"` / `"5V"` | `3` |
| 50 V | `50.0` または `"50 V"` / `"50V"` | `4` |
| 500 V | `500.0` または `"500 V"` / `"500V"` | `5` |
| 1000 V | `1000.0` または `"1000 V"` / `"1000V"` | `6` |

## AC 電圧レンジ

`set_mode("voltage_ac")` 後に指定する。

| ハードウェアレンジ | `set_range(value=...)` | `set_range(index=...)` |
|---|---:|---:|
| 500 mV | `0.5` または `"500 mV"` / `"500mV"` | `1` |
| 5 V | `5.0` または `"5 V"` / `"5V"` | `2` |
| 50 V | `50.0` または `"50 V"` / `"50V"` | `3` |
| 500 V | `500.0` または `"500 V"` / `"500V"` | `4` |
| 750 V | `750.0` または `"750 V"` / `"750V"` | `5` |

## DC 電流レンジ

`set_mode("current_dc")` 後に指定する。

| ハードウェアレンジ | `set_range(value=...)` | `set_range(index=...)` |
|---|---:|---:|
| 500 μA | `0.0005` または `"500 uA"` / `"500uA"` | `1` |
| 5 mA | `0.005` または `"5 mA"` / `"5mA"` | `2` |
| 50 mA | `0.05` または `"50 mA"` / `"50mA"` | `3` |
| 500 mA | `0.5` または `"500 mA"` / `"500mA"` | `4` |
| 5 A | `5.0` または `"5 A"` / `"5A"` | `5` |
| 10 A | `10.0` または `"10 A"` / `"10A"` | `6` |

## AC 電流レンジ

`set_mode("current_ac")` 後に指定する。

| ハードウェアレンジ | `set_range(value=...)` | `set_range(index=...)` |
|---|---:|---:|
| 500 μA | `0.0005` または `"500 uA"` / `"500uA"` | `1` |
| 5 mA | `0.005` または `"5 mA"` / `"5mA"` | `2` |
| 50 mA | `0.05` または `"50 mA"` / `"50mA"` | `3` |
| 500 mA | `0.5` または `"500 mA"` / `"500mA"` | `4` |
| 5 A | `5.0` または `"5 A"` / `"5A"` | `5` |
| 10 A | `10.0` または `"10 A"` / `"10A"` | `6` |

## 抵抗レンジ

`set_mode("resistance")` または `set_mode("fresistance")` 後に指定する。

| ハードウェアレンジ | `set_range(value=...)` | `set_range(index=...)` |
|---|---:|---:|
| 500 Ω | `500.0` または `"500 Ohm"` / `"500Ohm"` / `"500Ω"` | `1` |
| 5 kΩ | `5000.0` または `"5 kOhm"` / `"5kOhm"` / `"5kΩ"` | `2` |
| 50 kΩ | `50000.0` または `"50 kOhm"` / `"50kOhm"` / `"50kΩ"` | `3` |
| 500 kΩ | `500000.0` または `"500 kOhm"` / `"500kOhm"` / `"500kΩ"` | `4` |
| 5 MΩ | `5000000.0` または `"5 MOhm"` / `"5MOhm"` / `"5MΩ"` | `5` |
| 50 MΩ | `50000000.0` または `"50 MOhm"` / `"50MOhm"` / `"50MΩ"` | `6` |

## 静電容量レンジ

`set_mode("capacitance")` 後に指定する。

| ハードウェアレンジ | `set_range(value=...)` | `set_range(index=...)` |
|---|---:|---:|
| 50 nF | `50e-9` または `"50 nF"` / `"50nF"` | `1` |
| 500 nF | `500e-9` または `"500 nF"` / `"500nF"` | `2` |
| 5 μF | `5e-6` または `"5 uF"` / `"5uF"` | `3` |
| 50 μF | `50e-6` または `"50 uF"` / `"50uF"` | `4` |
| 500 μF | `500e-6` または `"500 uF"` / `"500uF"` | `5` |
| 5 mF | `5e-3` または `"5 mF"` / `"5mF"` | `6` |
| 50 mF | `50e-3` または `"50 mF"` / `"50mF"` | `7` |

## 温度センサ選択

`set_mode("temperature_rtd")` 後に指定する。

| ハードウェア選択肢 | `set_range(value=...)` | `set_range(index=...)` |
|---|---|---:|
| KITS90 | `"KITS90"` | `1` |
| PT100 | `"PT100"` | `2` |

## オートレンジ

| API | 内容 |
|---|---|
| `set_auto_range(True)` | オートレンジを有効にする。 |
| `set_auto_range(False)` | 直近の `set_range()` で保持している手動レンジを再設定する。 |

`set_auto_range(False)` の前には、少なくとも一度 `set_range()` を実行する必要がある。

## 内部測定速度

`set_integration_speed(speed)` で指定する。

| 指定値 | ハードウェア設定 | 測定速度 | 1 回の測定時間目安 | 用途 |
|---|---|---:|---:|---|
| `"F"` | High speed | 65 readings/s | 約 15.4 ms | 高速変化の監視 |
| `"M"` | Middle speed | 16 readings/s | 約 62.5 ms | Python からの安定取得 |
| `"S"` | Low speed | 4 readings/s | 約 250 ms | ノイズ低減・安定値取得 |

この速度は測定器内部の測定速度であり、Python からの SCPI 取得周期を保証しない。

## 測定実行

| API | 内容 |
|---|---|
| `meas(wait=None)` | 現在設定で 1 回測定する。 |
| `meas_continue(wait=None)` | 現在設定で連続測定を開始する。 |
| `get_result(clear=False)` | 直近の測定結果を取得する。 |

連続測定条件は次で指定する。

| API | 内容 |
|---|---|
| `set_continue_interval(interval)` | 連続測定の読み取り間隔を秒で指定する。 |
| `set_continue_duration(duration)` | 連続測定の最大時間を秒で指定する。 |
| `set_continue_count(count)` | 連続測定の最大点数を指定する。 |
