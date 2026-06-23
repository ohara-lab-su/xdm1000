# SCPI 採用方針

SCPI ドライバ層では、低レベル操作を明示的な Python メソッドとして提供する。上位制御層では SCPI コマンド名を利用者に意識させず、測定器として自然な API に集約する。

## CONFigure

`CONFigure:*` 系コマンドは、SCPI 層では個別メソッドとして提供する。

```text
configure_voltage_dc(range_value="AUTO")
configure_voltage_ac(range_value="AUTO")
configure_current_dc(range_value="AUTO")
configure_current_ac(range_value="AUTO")
configure_resistance(range_value="AUTO")
configure_fresistance(range_value="AUTO")
configure_frequency()
configure_period()
configure_capacitance(range_value="AUTO")
configure_temperature_rtd()
configure_diode()
configure_continuity()
```

ctrl 層ではこれらを `set_meas_mode(kind, range_value, rate)` に集約する。

## kind の対応

ctrl 層の `kind` は次の意味名である。

```text
voltage_dc       -> CONFigure:VOLTage:DC
voltage_ac       -> CONFigure:VOLTage:AC
current_dc       -> CONFigure:CURRent:DC
current_ac       -> CONFigure:CURRent:AC
resistance       -> CONFigure:RESistance
fresistance      -> CONFigure:FRESistance
frequency        -> CONFigure:FREQuency
period           -> CONFigure:PERiod
capacitance      -> CONFigure:CAPacitance
temperature_rtd  -> CONFigure:TEMPerature:RTD
diode            -> CONFigure:DIODe
continuity       -> CONFigure:CONTinuity
```

## RATE

SCPI 層では `set_rate(speed)` が `RATE {speed}` を送信する。値の正規化や検証は行わない。ctrl 層では `rate` 引数として上位 API から渡す。

## MEAS?

`MEAS?` は汎用測定値取得であり、応答が 1 値または 2 値になる可能性がある。SCPI 層では `meas_raw()` と `meas()` として公開する。

ctrl 層の標準測定では `MEAS?` ではなく `MEAS1?` を用いる。

## MEAS1?

`MEAS1?` は主表示値を取得する。SCPI 層では `meas_main()`、ctrl 層では 1shot / continuous / statistics の測定値取得に使う。

## MEAS2?

`MEAS2?` は副表示値を取得する。SCPI 層では `meas_sub()` として公開する。ctrl 層では現状公開していない。

## CALCulate:AVERage

SCPI 層には `set_calc_function_average()` と `get_average_all()` がある。`get_average_all()` は `CALCulate:AVERage:ALL?` の 4 要素応答を `AverageStats` に変換する。

ctrl 層の `start_statistics_mode()` は、`use_process=True` では `CALCulate:AVERage:ALL?` の結果を `stats` として保存する。ただし、装置側 statistics の clear/start 条件が未確認であるため、`duration` 秒の厳密な時間窓平均とは扱わない。

`use_process=False` の `start_statistics_mode()` は、ホスト側で `MEAS1?` を繰り返し、Python 側で最小・最大・平均・count を計算する。この点は process 使用時と実装が異なる。
