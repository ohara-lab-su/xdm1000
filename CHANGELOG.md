# Changelog

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