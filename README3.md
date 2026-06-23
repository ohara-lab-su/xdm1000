
## statistics mode API

### start_statistics_mode()

装置内部の statistics 機能を使うテスト測定を開始する。

```python
dmm.start_statistics_mode(
    kind="voltage_dc",
    duration=10.0,
    range_value="AUTO",
    rate="F",
)
```

内部処理

1. 測定モードを設定する。
2. `CALCulate:FUNCtion AVERage` を設定する。
3. 指定時間待つ。
4. `CALCulate:AVERage:ALL?` を読む。
5. result store に保存する。

これは時間窓平均 API ではない。
statistics の開始条件とリセット条件が実機で確認されるまで、
テスト機能として扱う。

---

# FastAPI server module

`server_fastapi/` は、

ローカル制御層を FastAPI / ese774_frame で公開するための別レイヤである。

`xdm1000_ctrl.py` 自体は FastAPI に依存しない。

---

## .pyi 生成

```bash
python -m xdm1000.server_fastapi.make
```

---

## サーバー起動

```bash
python examples/serve_xdm1000.py
```

---

## 測定サンプル

```bash
python examples/measure_xdm1000.py
```

---

## FastAPI 公開方針

FastAPI 側では、

`xdm1000_ctrl.py` の全メソッドを無条件に公開しない。

`server_fastapi/spec.py` で公開 API を選別する。

公開候補

- get_state()
- is_running()
- stop_job()
- get_continuous_result()
- get_statistics_result()
- set_measurement_mode()
- measure_one_shot()
- start_continuous_measurement()
- start_statistics_mode()

公開しないもの

- remote()
- local()
- raw SCPI
- query()
- write()

---

# 実装時の注意

- `xdm1000_scpi.py` の SCPI API を勝手に削らない。
- `xdm1000_ctrl.py` に `remote()` / `local()` を公開しない。
- コメントと docstring は日本語にする。
- `threading` を使わない。
- 長時間測定中の測定・設定 API は queue に積まず、親側で即拒否する。
- 状態取得と停止要求は command queue を通さない。
- continuous 測定の時刻は装置時刻ではなく host 側時刻である。
- statistics mode は時間窓平均として保証しない。
 