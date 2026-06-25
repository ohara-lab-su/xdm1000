# Changelog

## v0.2.0

### Changed

- 上位 API を全面的に見直した
  - `set_mode()` を中心とした状態保持型 API へ整理
  - 測定条件を ctrl / worker 間で一元管理する構成へ変更
  - `meas()` / `meas_continue()` が保持済み設定を利用する構成へ整理
- FastAPI 公開 API を整理
  - request / response model を見直し、API を再構成
  - API 名、引数、戻り値を統一した
- worker 構造を見直した
  - worker が設定状態を保持し、共有 state を通して ctrl と同期する構成へ変更
  - worker の設定キャッシュを API 仕様に合わせて整理
- client を見直した
  - API_SPEC に合わせて Sync / Async client を整理
  - `DeviceProxy("Xdm1000Ctrl", ...)` を正式な利用形とした
  - `config` による接続設定を共通利用できる構成へ整理

### Fixed

- API 全面変更後の ctrl / worker / client 間の不整合を修正
- Sync client が複数回 API を呼び出すと
  `Event loop is closed`
  および
  `cannot reuse already awaited coroutine`
  が発生する問題を修正
- Sync client が専用 event loop を保持し、同一 `httpx.AsyncClient` を継続利用する構成へ修正
- DeviceProxy(sync) 利用時の安定性を改善
- API 変更に伴う各 example を更新

### Docs

- API を全面更新
- README を API 仕様に合わせて更新
- サンプルコードを新 API に合わせて更新
 
## v0.1.2
 
- ドキュメント整備

## v0.1.1

- ドキュメント整備

## v0.1.0

### Changed

- 設定系を見直した
  - `config.py` の `Config` と yml を使う構成へ整理
  - `config` が与えられた場合は `PORT` / `TIMEOUT` / `BAUDRATE` などの設定を優先する構成へ変更
  - `config` が無い場合はコンストラクタ引数で設定できる構成へ整理
- 制御構造を見直した
  - `ctrl` / `worker` / `scpi` の責務を整理
  - `process` を使う構成と使わない構成を選択できるよう整理
  - `process` を使う場合は worker がシリアルポートを保持し、親側 `ctrl` は状態管理と RPC を担当する構成へ整理
- 測定条件の扱いを見直した
  - `set_meas_mode()` で保持した測定条件を `meas()` / `meas_xxx()` から再利用できるよう整理
  - `meas(パラメータ)` ではその呼び出しで与えた値を優先し、与えていない項目は既存設定を引き継ぐ構成へ整理
  - 同一条件では `CONFigure` / `RATE` を不要に再送しない構成へ整理
- ese774_frame 連携を見直した
  - `server_fastapi` 側から `DeviceProxy("Xdm1000Ctrl", ...)` を使うための登録経路を追加
  - Sync / Async client のコンストラクタを見直し、透過型の client として `config` を受けられる入口へ整理
- 実行例とテスト経路を見直した
  - `ctrl` / `scpi` の `main()` を単体動作確認用途で維持
  - direct 実行と process 実行の両方を確認しやすい構成へ整理

### Fixed

- `ctrl` / `worker` / `scpi` 間の I/F 不整合を修正
- worker 起動直後の `worker_ready` 同期不足に起因する timeout 系の不具合を修正
- worker 側の測定条件キャッシュ未初期化に起因する実行時エラーを修正
- `typing.Union` の import 漏れなど、worker import 時の実行時エラーを修正
- pyserial `Serial(...)` の引数指定を見直し、型エラーが起きにくい形へ修正
- `DeviceProxy` 経由利用時の client コンストラクタ不整合を修正
- Python 3.6 非互換となる書き方を見直した

### Docs

- docstring とコメントを全体的に見直した
- 構成方針、測定モード、worker の役割が分かるよう説明を追加した

## v0.0.1

- ドキュメントを若干整備/追加
- ctrl において、meas 関係が内部で毎度 set_voltage などをしているのを修正
  - meas の引数が同じ値のときは scip 側でセットし直さない

## v0.0.0

Initial release.

### Added

- Xdm1000Ctrl
- Xdm1000Scpi
- multiprocessing worker
- one-shot measurement
- pseudo continuous measurement
- statistics mode
- FastAPI server
- ese774_frame integration
- Sync/Async client
- measurement state management
- examples
- documentation