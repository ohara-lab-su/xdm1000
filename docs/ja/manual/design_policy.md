[![en](https://img.shields.io/badge/lang-en-red.svg)](https://ohara-lab-su.github.io/xdm1000/en/manual/design_policy.html) [![ja](https://img.shields.io/badge/lang-ja-blue.svg)](https://ohara-lab-su.github.io/xdm1000/ja/manual/design_policy.html)

# 設計方針

本ライブラリは、SCPI コマンド送受信、測定器としての上位操作、長時間測定、FastAPI 公開を分離する。

## 基本方針

- `xdm1000_scpi.py` は低レベル SCPI ドライバである。
- `xdm1000_ctrl.py` は測定器として扱う上位制御クラスである。
- `xdm1000_worker.py` は `use_process=True` の長時間測定と SCPI 実行を担う子プロセス側実装である。
- `server_fastapi/` は `Xdm1000Ctrl` を ese774_frame で透過公開する別レイヤである。
- `remote()` / `local()` / `query()` / `write()` は SCPI 層の責務であり、ctrl 層には公開しない。

## config 優先規則

`Xdm1000Scpi` と `Xdm1000Ctrl` は、`config` が渡された場合に `PORT`、`TIMEOUT`、`BAUDRATE` を config から取得する。config とコンストラクタ引数が同時に指定された場合は config を優先する。

## use_process

`Xdm1000Ctrl` は `use_process` を持つ。

- `use_process=True`: worker process を起動し、SCPI 通信を子プロセスへ隔離する。
- `use_process=False`: 同一プロセスで `Xdm1000Scpi` を直接生成する。長時間測定は呼び出し元スレッドをブロックする。

## 測定設定キャッシュ

測定種別、レンジ、レートはキャッシュされる。前回設定と同じ場合は不要な `CONFigure:*` と `RATE` の再発行を避ける。`kind`、`range_value`、`rate` を省略した API では、現在キャッシュまたは既定値を使う。

既定値は次である。

```text
kind        = voltage_dc
range_value = AUTO
rate        = F
```

## 長時間測定

長時間測定は `start_continuous_meas()` と `start_statistics_mode()` で開始する。`use_process=True` では開始要求は短時間で戻り、結果は `get_continuous_result()` または `get_statistics_result()` で取得する。`use_process=False` では同じ API 名だが、呼び出し元で測定ループを実行する。
