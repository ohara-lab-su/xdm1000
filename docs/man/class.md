# Xdm1000Ctrl

`Xdm1000Ctrl` は XDM1000 を測定器として扱うための上位制御クラスである。

SCPI コマンドを直接公開せず、測定用途に必要な API を提供する。

通常の利用では `Xdm1000Scpi` ではなく `Xdm1000Ctrl` を利用する。

---

# 役割

`Xdm1000Ctrl` の責務は次の通りである。

- 測定モード設定
- One Shot 測定
- 擬似 Continuous 測定
- Statistics 測定
- 測定状態管理
- Worker 管理
- FastAPI から利用する制御実体

SCPI コマンドの詳細は `Xdm1000Scpi` に閉じ込める。

---

# 初期化

代表的な初期化は次の通りである。

```python
from xdm1000.xdm1000_ctrl import Xdm1000Ctrl

dmm = Xdm1000Ctrl(
    port="/dev/cu.usbserial-10",
)
```

サーバー利用時は `FastApiServer` から生成されるため、通常は直接初期化しない。

---

# 設定値

主な設定値は次の通りである。

```python
port = "/dev/cu.usbserial-10"
timeout = 2.0
baudrate = 115200
```

`config` が渡された場合は、`PORT`, `TIMEOUT`, `BAUDRATE` を参照する。

---

# One Shot 測定

1 回だけ測定する。

```python
result = dmm.meas_one_shot(
    kind="voltage_dc",
    range_value="AUTO",
    rate="F",
    settle=0.0,
)
```

戻り値は dict である。

```python
{
    "kind": "voltage_dc",
    "range_value": "AUTO",
    "rate": "F",
    "value": -0.001551902,
    "host_time_start": 1782022977.959512,
    "host_time_end": 1782022978.470279,
    "read_elapsed": 0.5107839580014115,
}
```

`value` が測定値である。

---

# 短縮 API

代表的な測定には短縮 API を用意する。

```python
dmm.meas_voltage_dc()
dmm.meas_current_dc()
```

これらは内部で `meas_one_shot()` を呼ぶ。

---

# Continuous 測定

指定時間だけ測定を繰り返す。

```python
dmm.start_continuous_meas(
    kind="voltage_dc",
    duration=5.0,
    range_value="AUTO",
    rate="F",
    interval=0.0,
    settle=0.0,
)
```

`interval=0.0` の場合、Python 側では待機せず、装置と通信が許す範囲で最速に読む。

---

# Continuous 測定結果

測定完了後に結果を取得する。

```python
result = dmm.get_continuous_result(clear=True)
```

戻り値は dict である。

```python
{
    "job_id": "...",
    "ok": True,
    "stopped": False,
    "kind": "voltage_dc",
    "range_value": "AUTO",
    "rate": "F",
    "duration_requested": 5.0,
    "interval_requested": 0.0,
    "samples": [
        {
            "index": 0,
            "kind": "voltage_dc",
            "value": -0.0015,
            "host_time_start": 1782022977.0,
            "host_time_end": 1782022977.5,
            "t_rel_start": 0.0,
            "t_rel_end": 0.5,
            "read_elapsed": 0.5,
        }
    ],
    "stats": {
        "count": 1,
        "minimum": -0.0015,
        "maximum": -0.0015,
        "average": -0.0015,
    },
}
```

---

# Statistics 測定

XDM1000 内部の Statistics 機能を用いる。

```python
dmm.start_statistics_mode(
    kind="voltage_dc",
    duration=5.0,
    range_value="AUTO",
    rate="F",
    settle=0.0,
)
```

結果取得は次の通りである。

```python
result = dmm.get_statistics_result(clear=True)
```

Statistics はホスト側で sample を蓄積する Continuous 測定とは別機能である。

---

# 状態取得

現在の状態は `get_state()` で取得する。

```python
state = dmm.get_state()
```

代表的な項目は次の通りである。

```python
{
    "worker_alive": True,
    "running": False,
    "job_id": None,
    "job_type": None,
    "message": "worker_ready",
    "error": None,
}
```

---

# 実行中判定

```python
if dmm.is_running():
    print("running")
```

---

# 終了待ち

```python
dmm.wait_until_done(poll_interval=0.2)
```

`running` が `False` になるまで待機する。

---

# 停止要求

```python
dmm.stop_job()
```

停止要求は `stop_event` を通じて worker に伝える。
即時停止ではなく、worker が次の確認点で停止する。

---

# close / disconnect

```python
dmm.close()
```

または

```python
dmm.disconnect()
```

FastAPI サーバーでは lifespan 終了時に呼ばれる。

---

# 注意事項

`Xdm1000Ctrl` は SCPI を直接公開しない。
`remote()` や `local()` は `Xdm1000Scpi` 側の責務であり、上位 API としては公開しない。
長時間測定中に別の測定開始を行うことは想定しない。
状態確認、停止要求、結果取得は実行中でも利用する。