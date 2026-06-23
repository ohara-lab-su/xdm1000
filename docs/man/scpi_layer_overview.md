# SCPI ドライバ層の概要

`xdm1000_scpi.py` は OWON XDM1000 シリーズの SCPI コマンドをほぼ 1 対 1
に対応付ける低レベルドライバである。SCPI
の抽象化は最小限とし、装置マニュアルのコマンド体系をそのまま Python API
に反映することを目的とする。

## 主な機能

- IEEE488.2
    - `idn()`
    - `reset()`
- System
    - `remote()`
    - `local()`
    - `set_beeper()`
    - `get_beeper()`
- Configure
    - DC/AC 電圧
    - DC/AC 電流
    - 2 線抵抗
    - 4 線抵抗
    - 周波数
    - 周期
    - 容量
    - RTD 温度
    - ダイオード
    - 導通
- Sense
    - 測定機能選択
    - レンジ
    - AUTO/MANUAL
    - Rate(F/S/M)
    - 温度設定
    - NULL
    - dB / dBm
- Measure
    - `meas()`
    - `meas_main()`
    - `meas_sub()`

本クラスは SCPI ドライバであり、測定シーケンスの管理は行わない。

## 測定速度

OWON の仕様では積分時間(NPLC)ではなく `Rate` を使用する。

- Fast
- Medium
- Slow

Fast は高速更新、Slow
はノイズ性能を優先する。詳細な更新速度・確度はユーザーマニュアルおよび
Programming Manual に従う。

---
