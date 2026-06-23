# SCPI ドライバ API リファレンス

`xdm1000_scpi.py` は低レベル SCPI API を提供する。

## AverageStats

`CALCulate:AVERage:ALL?` の結果を保持する単純なクラスである。

```text
minimum
maximum
average
count
```

## Xdm1000Scpi 初期化

```python
Xdm1000Scpi(
    port,
    timeout=1.0,
    baudrate=115200,
    logger=None,
    logger_name=None,
    log_level=None,
    config=None,
)
```

`config` がある場合は `PORT`、`TIMEOUT`、`BAUDRATE`、`LOGGER_LEVEL` を優先する。最終的に `port` がない場合は `ValueError` である。

## ライフサイクル

### close()

シリアルポートを閉じる。

### disconnect()

`close()` の別名である。

### __del__()

破棄時に `local()` を試行し、その後 `close()` を試行する。

## 基本通信

### write(command)

SCPI コマンドを送信する。末尾に改行がなければ LF を付加する。

### query(command)

SCPI クエリを送信し、1 行の応答文字列を返す。送信前に受信バッファをクリアする。応答が空の場合は `TimeoutError` である。

### query_float(command)

`query(command)` の結果を float に変換して返す。

### query_int(command)

`query(command)` の結果を float 経由で int に変換して返す。

## IEEE 488.2

### idn()

`*IDN?` を送信し、識別文字列を返す。

### reset()

`*RST` を送信する。現状の実装では `*RST` を2回送信する。

## System

### remote()

`SYSTem:REMote` を送信する。

### local()

`SYSTem:LOCal` を送信する。

### set_beeper(enabled)

`SYSTem:BEEPer:STATe ON/OFF` を送信する。

### get_beeper()

`SYSTem:BEEPer:STATe?` を取得し、0 以外を True として返す。

## Configure

### configure_voltage_dc(range_value="AUTO")

`CONFigure:VOLTage:DC {range_value}` を送信する。

### configure_voltage_ac(range_value="AUTO")

`CONFigure:VOLTage:AC {range_value}` を送信する。

### configure_current_dc(range_value="AUTO")

`CONFigure:CURRent:DC {range_value}` を送信する。

### configure_current_ac(range_value="AUTO")

`CONFigure:CURRent:AC {range_value}` を送信する。

### configure_resistance(range_value="AUTO")

`CONFigure:RESistance {range_value}` を送信する。

### configure_fresistance(range_value="AUTO")

`CONFigure:FRESistance {range_value}` を送信する。

### configure_frequency()

`CONFigure:FREQuency` を送信する。

### configure_period()

`CONFigure:PERiod` を送信する。

### configure_capacitance(range_value="AUTO")

`CONFigure:CAPacitance {range_value}` を送信する。

### configure_temperature_rtd()

`CONFigure:TEMPerature:RTD` を送信する。

### configure_diode()

`CONFigure:DIODe` を送信する。

### configure_continuity()

`CONFigure:CONTinuity` を送信する。

## CALCulate

### set_calc_function_average()

`CALCulate:FUNCtion AVERage` を送信する。

### get_average_all()

`CALCulate:AVERage:ALL?` を取得し、4 要素の応答を `AverageStats` として返す。要素数が4でない場合は `ValueError` である。

## RATE

### set_rate(speed)

`RATE {speed}` を送信する。実装上は値検証をしない。

### get_rate()

`RATE?` の文字列応答を返す。

## Measure

### meas_raw()

`MEAS?` の応答を文字列のまま返す。

### meas()

`MEAS?` のカンマ区切り応答を float 化する。1 要素なら float、2 要素なら `(main, sub)` の tuple を返す。それ以外は `ValueError` である。

### meas_main()

`MEAS1?` を float として返す。

### meas_sub()

`MEAS2?` を float として返す。
