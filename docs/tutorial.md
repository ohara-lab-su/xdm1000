# チュートリアル

この文書では、XDM1000 を実際に動かすための最小手順を示す。

詳細な設計は `docs/architecture.md`、SCPI 層は `docs/scpi.md`、上位制御クラスは `docs/ctrl.md` を参照する。

---

# 1. 接続確認

XDM1000 を USB で接続し、シリアルポート名を確認する。

macOS の例:

```bash
ls /dev/cu.*
```

例:

```text
/dev/cu.usbserial-10
```

以後の例では次を使用する。

```python
PORT = "/dev/cu.usbserial-10"
```

---

# 2. ローカル利用

FastAPI を使わず、Python から直接 `Xdm1000Ctrl` を使う。

```python
from xdm1000.xdm1000_ctrl import Xdm1000Ctrl


PORT = "/dev/cu.usbserial-10"


def main():
    dmm = Xdm1000Ctrl(port=PORT)

    try:
        print(dmm.idn())
        print(dmm.meas_one_shot("voltage_dc"))

    finally:
        dmm.close()


if __name__ == "__main__":
    main()
```

---

# 3. DC 電圧を 1 回測定する

```python
result = dmm.meas_one_shot(
    kind="voltage_dc",
    range_value="AUTO",
    rate="F",
    settle=0.0,
)
```

戻り値の例:

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

---

# 4. 短縮 API

DC 電圧測定:

```python
result = dmm.meas_voltage_dc()
```

DC 電流測定:

```python
result = dmm.meas_current_dc()
```

---

# 5. 測定モードを先に設定する

```python
dmm.set_meas_mode(
    kind="voltage_dc",
    range_value="AUTO",
    rate="F",
)
```

その後、測定する。

```python
result = dmm.meas_one_shot("voltage_dc")
```

---

# 6. Continuous 測定

指定時間だけ繰り返し測定する。

```python
dmm.start_continuous_meas(
    kind="voltage_dc",
    duration=5.0,
    range_value="AUTO",
    rate="F",
    interval=0.0,
    settle=0.0,
)

dmm.wait_until_done()

result = dmm.get_continuous_result(clear=True)
```

`interval=0.0` の場合、Python 側では追加待機を行わず、装置と通信が許す範囲で連続して読む。

---

# 7. Continuous 測定中の状態確認

```python
state = dmm.get_state()
print(state)
```

実行中判定:

```python
print(dmm.is_running())
```

---

# 8. Continuous 測定の停止

```python
dmm.stop_job()
```

停止は即時強制終了ではない。

worker が停止要求を確認した時点で終了する。

---

# 9. Statistics 測定

装置内部 Statistics を利用する。

```python
dmm.start_statistics_mode(
    kind="voltage_dc",
    duration=5.0,
    range_value="AUTO",
    rate="F",
    settle=0.0,
)

dmm.wait_until_done()

result = dmm.get_statistics_result(clear=True)
```

Statistics はホスト側で sample を蓄積する Continuous 測定とは別機能である。

---

# 10. FastAPI サーバー起動

`examples/serve_start.py` を実行する。

```bash
python examples/serve_start.py
```

起動後、以下のように表示される。

```text
Uvicorn running on http://127.0.0.1:8000
```

---

# 11. クライアントから測定する

`examples/client_meas_volt.py` を実行する。

```bash
python examples/client_meas_volt.py
```

最小例:

```python
from xdm1000.server_fastapi.clients.sync_xdm1000_client import SyncXdm1000Client


HOST = "127.0.0.1"
PORT = 8000


def main():
    dmm = SyncXdm1000Client(HOST, PORT)

    print(dmm.meas_one_shot("voltage_dc"))


if __name__ == "__main__":
    main()
```

---

# 12. FastAPI 経由の API path

API path は次の形式である。

```text
POST /instance/xdm1000/<api_name>
```

例:

```text
POST /instance/xdm1000/meas_one_shot
POST /instance/xdm1000/get_state
POST /instance/xdm1000/start_continuous_meas
POST /instance/xdm1000/get_continuous_result
```

---

# 13. よく使う測定種別

```python
"voltage_dc"
"voltage_ac"
"current_dc"
"current_ac"
"resistance"
"fresistance"
"frequency"
"period"
"capacitance"
"temperature_rtd"
"diode"
"continuity"
```

---

# 14. 終了処理

ローカル利用では最後に閉じる。

```python
dmm.close()
```

または

```python
dmm.disconnect()
```

FastAPI サーバー利用時は lifespan 終了時に処理される。