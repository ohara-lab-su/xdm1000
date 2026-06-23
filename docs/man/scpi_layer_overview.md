# SCPI ドライバ層の概要

`xdm1000_scpi.py` は OWON XDM1000/XDM1241 系デジタルマルチメータに SCPI コマンドを送る低レベルドライバである。pyserial を内包し、ASCII テキストの SCPI コマンド送信、応答取得、基本的な型変換を行う。

## 主な責務

- `serial.Serial` の生成と解放
- SCPI `write()` / `query()`
- `query_float()` / `query_int()` による基本型変換
- IEEE 488.2 の `idn()` / `reset()`
- System の `remote()` / `local()` / beeper 設定
- `CONFigure:*` による測定機能・レンジ設定
- `RATE` による測定速度設定
- `MEAS?` / `MEAS1?` / `MEAS2?` による測定値取得
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

## 測定速度

現状の実装は `RATE {speed}` と `RATE?` を使う。`speed` は文字列で指定する。

ソースコード上の docstring では `F`、`M`、`L` と記載されている。一方、ctrl 層の引数説明では `F`、`M`、`S` と記載されている。現状の実装は値の検証を行わず、渡された文字列をそのまま `RATE` に渡す。

## 測定値取得

- `meas_raw()` は `MEAS?` の生文字列を返す。
- `meas()` は `MEAS?` を float または 2 要素 tuple に変換する。
- `meas_main()` は `MEAS1?` を float として返す。
- `meas_sub()` は `MEAS2?` を float として返す。

ctrl 層の 1shot / continuous / statistics では主表示値取得として `meas_main()`、すなわち `MEAS1?` を使う。
