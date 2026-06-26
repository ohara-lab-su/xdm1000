# Changelog

## v0.2.4

サーバーとクライアントを ```127.0.0.1``` 以外で起動したことで、
アホなバグが色々と発覚、修正

### Changed

- うっかりしていたアホなバグを修正： 設定処理を全面的に整理
  - `Config` を設定情報を保持するオブジェクトとして明確化
  - YAML の読み込み責務を `Config` に集約
  - Control / SCPI / Worker は `Config` オブジェクトまたはコンストラクタ引数のみを受け付ける構成へ整理
  - `Config` を利用しない場合はコンストラクタ引数のみで動作する構成へ整理
  - コンストラクタ引数が指定された場合は `Config` の設定より優先する仕様へ整理

- うっかりしていたアホなバグを修正: ネットワーク設定を整理
  - `SERVER_HOST` を正式名称へ統一
  - `SERVER_IP` は後方互換として継続サポート
  - `host` を正式なコンストラクタ引数へ統一
  - `ip` は後方互換として継続サポート

- サンプルプログラムを整理
  - YAML ファイルを直接渡す構成を廃止
  - `Config` オブジェクトを生成して利用する構成へ統一

- サーバー起動処理を整理
  - `SERVER_HOST` / `SERVER_PORT` を `Config` オブジェクトから取得する構成へ整理
  - ログ出力と実際の起動設定が一致するよう整理

### Fixed

- `SERVER_HOST` と `SERVER_IP` の混在に起因する設定取得の不整合を修正
- Config 利用時とコンストラクタ利用時で設定解決が一致しない問題を修正
- サーバー起動時にログ出力と実際の待受ポートが一致しない問題を修正
- Client / Control / Worker 間の設定受け渡しに関する不整合を修正

### Docs

- 設定方法に関する説明を更新
- `Config` の責務と各レイヤーの役割を明確化
- `SERVER_HOST` を正式名称とすることをドキュメントへ反映
- 
## v0.2.3

### Changed

- 制御 API のレンジ指定を改善
  - `set_range()` を物理量指定とレンジ番号指定の両方に対応
  - `value` と `index` の排他指定へ変更
  - レンジ番号専用 API を廃止し、`set_range()` に統合

- レンジ指定の入力形式を改善
  - 単位付き文字列を受け付けるよう改善
    - `"500mV"`
    - `"500 mV"`
    - `"5V"`
    - `"5 V"`
    - `"50kΩ"`
    - `"50 kOhm"` など
  - 数値指定では各測定モードの基本単位として扱う仕様を追加
    - DCV / ACV : V
    - DCI / ACI : A
    - Resistance : Ω
    - Capacitance : F

- レンジ変換を Control 層へ移動
  - SCPI 層はハードウェア仕様に沿った薄いラッパとして維持
  - Control 層で物理量から SCPI の離散レンジ番号へ変換する構成へ整理

- レンジ指定時の検証を改善
  - 現在の測定モードに対応しないレンジを検出
  - `value` と `index` の同時指定を禁止

- API 仕様を更新
  - Control API リファレンスを現行実装へ更新
  - Control Layer ドキュメントを更新
  - ハードウェア仕様と Control API の対応表を追加
  - 測定モード・レンジ・測定速度の一覧を追加

### Added

- ハードウェア仕様書
  - XDM1241 の測定モード一覧
  - 各測定モードの選択可能レンジ一覧
  - 測定速度一覧
  - Control API 対応一覧

## v0.2.2

### Changed

- クライアント API の同期・非同期設計を改善
  - Sync クライアントは同期 API、Async クライアントは非同期 API として自然に利用できるよう整理
  - フレームワークによる自動生成メソッドがデバイス固有実装を上書きしない構成に対応

- 非同期測定 API を改善
  - `wait_until_done()` はクライアント側ポーリングで待機する構成を維持
  - サーバー側では測定を継続しながら他クライアントから状態取得・停止・結果取得を行える構成を維持

- worker の制御性を改善
  - 非同期測定中でも制御要求を受け付けられるよう worker の状態管理を改善
  - 測定処理と制御処理の分離を整理し、複数クライアントからの利用を考慮した実装へ改善

- ログ出力を整理
  - 高頻度で呼び出される状態監視 API を考慮し、クライアント側の不要なログ出力を整理
  - サーバー側アクセスログとの役割を明確化

## v0.2.1

### Changed

- 非同期測定 API を見直した
  - `wait_until_done()` をクライアント側ポーリング方式へ変更
  - サーバー側は測定処理を継続したまま他クライアントから状態取得できる構成へ整理
- worker の非同期測定処理を改善
  - 測定中でも `is_running()`、`stop()`、`get_result()` を処理できるよう設計を見直した
  - worker のイベントループと制御要求の共存性を改善
- API の振る舞いを整理
  - ローカル実行とサーバー実行で同一 API を利用できるよう整理
  - 非同期測定の状態遷移を整理

### Added

- `is_running()`
- `wait_until_done()`
- `stop()`
- `get_result()`
- 非同期測定のサンプルプログラム
- 非同期測定チュートリアル

### Fixed

- 非同期測定中に他クライアントから制御できない問題を修正
- 非同期測定結果取得処理を修正
- worker のジョブ管理を修正
 
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