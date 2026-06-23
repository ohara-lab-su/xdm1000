# 設計方針

本ファイルは、`xdm1000_scpi.py` と `xdm1000_ctrl.py` の分離方針、および SCPI コマンド採用方針をまとめる。

- `xdm1000_scpi.py` は SCPI を低レベル API として提供する。
- SCPI コマンドは削らない。
- `remote()` / `local()` は SCPI 層にのみ置く。
- `xdm1000_ctrl.py` は測定器として扱う上位制御層である。
- ctrl 層では SCPI を隠蔽し、`remote()` / `local()` は公開しない。

## 設計目的

- ローカル制御クラスとして設計する。
- FastAPI や ese774_frame には依存しない。
- サーバープロセスで実体化されることを前提とする。
- 長時間測定は multiprocessing.Process を使用する。
- 測定中は running 状態を保持する。
