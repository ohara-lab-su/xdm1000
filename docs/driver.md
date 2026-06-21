# SCPI ドライバ

`xdm1000_scpi.py` は XDM1000 シリーズの SCPI コマンドをほぼ 1 対 1 に対応付ける低レベルドライバである。

上位の測定制御は一切行わず、Programming Manual のコマンド体系をそのまま Python メソッドへ写像することを目的とする。

---

# 設計方針

SCPI ドライバは

- SCPI コマンド送信
- SCPI 応答受信
- 型変換

のみを担当する。

以下は担当しない。

- 長時間測定
- running 管理
- multiprocessing
- 測定シーケンス
- 状態管理

これらはすべて `Xdm1000Ctrl` の責務である。

---

# SCPI サブシステム

Programming Manual に従い、各サブシステムをそのまま実装する。

## IEEE488.2

共通コマンドである。

例

- `*IDN?`
- `*RST`

対応メソッド

- `idn()`
- `reset()`

---

## SYSTem

装置全体の設定を行う。

例

- Remote
- Local
- Beeper

対応メソッド

- `remote()`
- `local()`
- `set_beeper()`
- `get_beeper()`

remote/local は SCPI ドライバのみが公開する。

上位制御クラスからは公開しない。

---

## CONFigure

測定ファンクションを切り替える。

例

- DC Voltage
- AC Voltage
- Current
- Resistance
- Capacitance
- Frequency
- Temperature

対応メソッド

- `configure_voltage_dc()`
- `configure_voltage_ac()`
- `configure_current_dc()`
- `configure_current_ac()`
- `configure_resistance()`
- `configure_fresistance()`
- `configure_frequency()`
- `configure_period()`
- `configure_capacitance()`
- `configure_temperature_rtd()`
- `configure_diode()`
- `configure_continuity()`

---

## SENSe

現在の測定条件を設定する。

例

- Function
- Rate
- Temperature
- Continuity

対応メソッド

- `set_function()`
- `get_function()`
- `set_rate()`
- `get_rate()`
- `set_temperature_rtd_type()`
- `set_temperature_unit()`
- `set_temperature_show()`

---

## CALCulate

測定後に内部 Statistics を利用する機能である。

時間平均ではない。

XDM1000 内部が保持する Statistics バッファを参照する。

対応メソッド

- `get_average_all()`
- `get_average()`
- `get_average_maximum()`
- `get_average_minimum()`
- `set_calc_state()`
- `set_calc_function()`
- `set_db_reference()`
- `set_dbm_reference()`
- `set_null_offset()`

Statistics モード確認用として `Xdm1000Ctrl` から利用する。

---

# MEAS コマンド

Programming Manual には三種類の測定コマンドが存在する。

## MEAS?

現在表示されている測定値全体を取得する。

副表示が有効な場合は

```
main,sub
```

を返す。

対応メソッド

- `meas_raw()`
- `meas()`

---

## MEAS1?

主表示値のみ取得する。

対応メソッド

- `meas_main()`

本ライブラリでは通常はこちらを利用する。

---

## MEAS2?

副表示値のみ取得する。

対応メソッド

- `meas_sub()`

副表示を利用する特殊用途のみ使用する。

---

# Xdm1000Ctrl における採用方針

```
One Shot
↓
MEAS1?
```
```
Continuous
↓
MEAS1?
```

を繰り返し取得する。
```
Statistics
↓
CALCulate
```

を利用する。

SCPI ドライバではどのコマンドも削除しない。
上位制御が利用しない SCPI についても、Programming Manual に存在するものは可能な限り実装することを方針とする。

---

# 測定速度

XDM1000 は NPLC ではなく Rate を使用する。

設定値

- F
- M
- L

それぞれ

- Fast
- Medium
- Low

を意味する。
更新速度および測定確度は Programming Manual に従う。

---

# 注意事項

SCPI ドライバは単なる通信層である。
running 管理や multiprocessing は一切行わない。
利用者が通常直接利用することは想定しておらず、`Xdm1000Ctrl` を利用することを推奨する。