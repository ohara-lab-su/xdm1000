# 実装上の注意事項

- `xdm1000_ctrl.py` に `remote()` / `local()` を公開しない。
- 長時間測定中の測定・設定 API は queue に積まず、親側で即拒否する。
- 状態取得と停止要求は command queue を通さない。
- continuous 測定の時刻は装置時刻ではなく host 側時刻である。
- statistics mode は時間窓平均として保証しない。
