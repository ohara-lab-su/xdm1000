# コボッタ制御
view on [github](https://github.com/ohara-lab-su/cobotta2/) / [ohara-lab-su (doc)](https://ohara-lab-su.github.io/)

---
```{toctree}
:maxdepth: 2
:caption: Contents:

api/modules
archtecture
class
driver
tutorial
```
---

OWON XDM1000 シリーズデジタルマルチメータ用 Python 制御ライブラリである。

本ライブラリは XDM1000 を Python からローカル制御できることを第一目的として設計している。また、その制御クラスをそのまま FastAPI サーバーへ組み込み、ese774_frame を介したリモート制御を実現することも目的としている。

SCPI を直接利用する低レベルドライバと、測定器として利用するための上位制御クラスを明確に分離している。

---

# 特徴

- XDM1000 Series Programming Manual に対応した SCPI ドライバ
- SCPI を隠蔽した上位制御クラス
- ローカル制御・リモート制御の両対応
- multiprocessing を利用した長時間測定
- 擬似 continuous 測定
- statistics モード
- FastAPI サーバー対応
- ese774_frame 自動 API 生成対応

---

# ディレクトリ構成

```text
project_root/
├── src/
│   └── xdm1000/
│       ├── xdm1000_scpi.py
│       ├── xdm1000_ctrl.py
│       ├── xdm1000_worker.py
│       └── server_fastapi/
│           ├── spec.py
│           ├── make.py
│           ├── models/
│           ├── routers/
│           └── clients/
│
├── examples/
│   ├── serve_start.py
│   └── client_meas_volt.py
│
├── README.md
├── TUTORIAL.md
├── API_REFERENCE.md
└── CHANGELOG.md
```

---

# 設計方針

本ライブラリはレイヤ分離を最優先として設計している。

```
Application
      │
      ▼
Xdm1000Ctrl
      │
      ▼
Xdm1000Scpi
      │
      ▼
USB Serial
      │
      ▼
XDM1000
```

SCPI の知識は xdm1000_scpi.py のみに集約する。

利用者は通常 xdm1000_ctrl.py のみを利用する。

FastAPI から利用する場合も、サーバー側で実体化されるのは Xdm1000Ctrl であり、SCPI ドライバを直接公開しない。

SCPI ドライバは装置仕様との対応を保つことを目的とする。

一方、上位制御クラスは「測定器として利用する API」を提供することを目的とする。

そのため、SCPI コマンド体系と上位 API は一致しない。

```
Xdm1000Ctrl
        │
        ├── one shot
        ├── continuous
        ├── statistics
        ├── state
        └── worker process

            │

Xdm1000Scpi
        │
        ├── CONFigure
        ├── SENSe
        ├── MEAS
        ├── CALCulate
        └── IEEE488.2
```

この構造により、

- SCPI の変更
- API の変更
- FastAPI の変更

を互いに独立して行うことができる。

---

# SCPI ドライバ (`xdm1000_scpi.py`)

## 設計目的

`xdm1000_scpi.py` は XDM1000 Programming Manual に記載されている SCPI コマンドを、そのまま Python メソッドとして提供する低レベルドライバである。

このクラスの目的は、

- SCPI コマンドを隠蔽しないこと
- マニュアルとの対応を明確にすること
- 上位制御から SCPI の詳細を分離すること

である。

SCPI ドライバ自身は測定シーケンスを持たない。

例えば、

- one shot
- continuous
- statistics

などの概念は持たない。

SCPI を送信し、その結果を返すだけである。

---

## SCPI 採用方針

本ライブラリでは Programming Manual に存在する SCPI は、利用頻度に関係なく原則として実装する。

上位制御で利用しない SCPI も削除しない。

これは

- デバッグ
- 装置検証
- 将来の拡張

を容易にするためである。

---

## SCPI サブシステム

実装は Programming Manual の章構成に合わせている。

### IEEE488.2

装置識別やリセットなどの共通コマンドを提供する。

例

- *IDN?
- *RST

---

### SYSTem

装置設定を行う。

例

- Remote
- Local
- Beeper

Remote / Local の切替は SCPI ドライバのみが保持する責務であり、上位制御クラスでは公開しない。

---

### CONFigure

測定機能そのものを切り替える。

例

- DC Voltage
- AC Voltage
- DC Current
- Resistance
- Frequency
- Continuity

通常は一度設定すると、その測定モードで動作し続ける。

---

### SENSe

測定条件を設定する。

例

- Range
- Rate
- Temperature
- dB
- Null

測定機能(CONFigure)とは独立して設定される。

---

### MEASure

測定値を取得する。

Programming Manual には複数の取得方法が存在する。

#### MEAS?

主表示・副表示をまとめて取得する。

副表示が存在する場合は

```
main,sub
```

が返る。

#### MEAS1?

主表示のみ取得する。

本ライブラリでは通常の測定値取得はこれを採用している。

#### MEAS2?

副表示のみ取得する。

通常の測定では使用しないが、SCPI ドライバでは提供する。

---

### CALCulate

演算機能である。

本ライブラリでは

- NULL
- dB
- dBm
- Statistics

を提供する。

Statistics は装置内部の統計機能であり、ホスト側で一定時間平均を取る continuous 測定とは目的が異なる。

---

# 上位制御クラス (`xdm1000_ctrl.py`)

## 設計目的

上位制御クラスは XDM1000 を「測定器」として扱うための API を提供する。

利用者は SCPI を意識する必要はない。

例えば

```python
dmm.meas_one_shot("voltage_dc")
```

だけで

- CONFigure
- RATE
- MEAS1?

など必要な SCPI を内部で実行する。

---

## SCPI の隠蔽

上位制御クラスでは

- remote()
- local()

を公開しない。

これらは SCPI ドライバ内部のみが扱う。

利用者は

- 測定
- 設定

のみを意識すればよい。

---

## 測定モード

上位制御では次の三種類を提供する。

### One Shot

1回だけ測定する。

内部では

```
CONFigure
↓
RATE
↓
MEAS1?
```

を実行する。

---

### Continuous

指定時間だけ最速または指定間隔で測定する。
SCPI に continuous 測定は存在しない。
そのため

```
MEAS1?
↓
MEAS1?
↓
MEAS1?
```

をホスト側で繰り返し実行する。
各測定値には

- host start time
- host end time

を保存する。

---

### Statistics

装置内部 Statistics 機能を利用する。
これは XDM1000 が内部で保持する統計値を取得するモードであり、continuous 測定とは別機能である。
現状では動作確認用機能として提供する。


---
## 作者
- Kengo NAKADA
