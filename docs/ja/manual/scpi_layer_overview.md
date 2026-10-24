[![en](https://img.shields.io/badge/lang-en-red.svg)](https://ohara-lab-su.github.io/xdm1000/en/manual/scpi_layer_overview.html) [![ja](https://img.shields.io/badge/lang-ja-blue.svg)](https://ohara-lab-su.github.io/xdm1000/ja/manual/scpi_layer_overview.html)

# SCPI ドライバ層の概要

`xdm1000_scpi.py` は OWON XDM1000/XDM1241 系デジタルマルチメータに SCPI コマンドを送る低レベルドライバである。pyserial を内包し、ASCII テキストの SCPI コマンド送信、応答取得、基本的な型変換を行う。

## 主な責務

- `serial.Serial` の生成と解放
- SCPI `write()` / `query()`
- `query_float()` / `query_int()` による基本型変換
- IEEE 488.2 の `idn()` / `reset()`
- System の `remote()` / `local()` / beeper 設定
- `CONFigure:*` 系コマンドの薄いラッパ
- `FUNCtion` / `FUNCtion?`
- `RANGE`
- `AUTO` / `AUTO?`
- `RATE` / `RATE?`
- `MEAS?` / `MEAS1?` / `MEAS2?`
- `CALCulate:AVERage:ALL?` の構造化

## 通信仕様

シリアル通信は 8-N-1、フロー制御なしで開く。

```python
serial.Serial(
    port=port,
    baudrate=baudrate,
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=timeout,
    write_timeout=timeout,
    xonxoff=False,
    rtscts=False,
    dsrdtr=False,
)
```

## ctrl 層との関係

SCPI 層は上位 API の状態管理を持たない。`set_mode()`、`set_range()`、`meas_continue()`、`get_result()` などの利用者向け API、worker process、設定キャッシュ、結果キャッシュは ctrl 層の責務である。

ctrl 層の標準測定値取得は `meas_main()`、すなわち `MEAS1?` を使う。
