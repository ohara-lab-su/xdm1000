# SCPI 採用方針

SCPI ドライバ層は、測定器が受け付ける SCPI コマンドを薄く Python メソッドに写す層である。上位 ctrl API の都合に合わせて SCPI 層を高級化しない。

## SCPI 層と ctrl 層の分担

SCPI 層は以下を担当する。

- `write()` / `query()` による SCPI 送受信
- `*IDN?`、`*RST`、`SYSTem:REMote`、`SYSTem:LOCal`
- `CONFigure:*` 系コマンドの薄いラッパ
- `FUNCtion` / `FUNCtion?`
- `RANGE`
- `AUTO` / `AUTO?`
- `RATE` / `RATE?`
- `MEAS?` / `MEAS1?` / `MEAS2?`
- `CALCulate:AVERage:ALL?`

ctrl 層は以下を担当する。

- 利用者向けの `set_mode()` / `set_range()` / `set_auto_range()` / `set_integration_speed()`
- 単発測定入口 `meas()`
- 連続測定入口 `meas_continue()`
- 連続測定の周期・終了条件
- worker process、設定キャッシュ、結果キャッシュ

## CONFigure と FUNCtion / RANGE の扱い

`CONFigure:*` は SCPI コマンドそのものである。SCPI 仕様上、`CONFigure:VOLTage:DC <range>` のように測定機能とレンジを同時に扱う形式があるため、SCPI 層ではその形の薄いラッパを残す。

ただし ctrl 層の標準設定 API では `CONFigure:*` を使わず、次の独立系 SCPI を使う。

```text
FUNCtion "..."    # 測定モード
RANGE <value>     # 測定レンジ
AUTO              # オートレンジ有効化
RATE <F|M|S>      # 内部測定速度
```

これにより、ctrl 層の `set_mode()` と `set_range()` が混ざらない。

## RATE

SCPI コマンド名は `RATE` である。ctrl 層では測定点間隔と混同しないように `integration_speed` と呼ぶ。値は `F`、`M`、`S` を受け付ける。

## MEAS 系

ctrl 層の標準測定値取得は主表示値取得として `MEAS1?`、すなわち SCPI 層の `meas_main()` を使う。

`MEAS?` は主表示・副表示を含む可能性があるため、SCPI 層には `meas_raw()` / `meas()` として残すが、ctrl の標準測定 API では使わない。
