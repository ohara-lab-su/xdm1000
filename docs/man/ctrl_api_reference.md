# ctrl API リファレンス

`xdm1000_ctrl.py` は上位制御層である。
SCPI ドライバ層の API をそのまま公開するものではない。
利用者は測定器として必要な操作だけを呼ぶ。

---

## ライフサイクル

### close()

worker process を終了し、シリアルポートを閉じる。
`remote()` / `local()` は ctrl 層には存在しない。
これらは `xdm1000_scpi.py` の低レベル API としてのみ提供する。

---

## 状態取得 API

### get_state()

現在の状態を返す。
running 中でも呼び出せる。
command queue を通さず、
親プロセスが保持する state を直接読む。

戻り値の例

```python
{
    "running": True,
    "job_type": "continuous",
    "job_id": "xxxx",
    "meas_mode": "voltage_dc",
    "range": "AUTO",
    "rate": "F",
    "started_time": 1710000000.0,
    "finished_time": None,
    "sample_count": 123,
    "last_value": 1.234,
    "message": "running",
    "error": None,
}
```

---

### is_running()

長時間測定中かを bool で返す。
内部的には state の `running` を見る。

---

### stop_job()

実行中の長時間測定へ停止要求を出す。
この API は command queue を使わない。
親プロセスが stop event を立てる。
worker process は測定ループ中に stop event を監視し、
停止要求を検出したら安全に測定を終了する。

---

## 結果取得 API

### get_continuous_result()

continuous 測定の結果を返す。
原則として測定終了後に呼ぶ。
戻り値には測定サンプル列と統計情報を含める。

例

```python
{
    "job_type": "continuous",
    "meas_mode": "voltage_dc",
    "range": "AUTO",
    "rate": "F",
    "duration": 10.0,
    "interval": 0.0,
    "sample_count": 100,
    "samples": [
        {
            "index": 0,
            "value": 1.234,
            "host_time_start": 1710000000.000,
            "host_time_end": 1710000000.025,
            "elapsed": 0.025,
        }
    ],
    "statistics": {
        "minimum": 1.230,
        "maximum": 1.240,
        "average": 1.235,
    },
}
```

---

### get_statistics_result()

statistics mode の結果を返す。

これは `CALCulate:AVERage:ALL?` の結果を保持する。

時間窓平均ではない。

---

## 測定設定 API

### set_meas_mode()

測定モードを設定する。

```python
dmm.set_meas_mode(
    kind="voltage_dc",
    range_value="AUTO",
    rate="F",
)
```

`kind` は ctrl 層の意味名である。

利用可能な値

```text
voltage_dc
voltage_ac
current_dc
current_ac
resistance
fresistance
frequency
period
capacitance
temperature_rtd
diode
continuity
```

内部では

- `CONFigure:*`
- `SENSe:RATE`

を呼ぶ。

running 中は実行できない。

running 中に呼ばれた場合は

```python
DeviceBusyError
```

を返す。

---

## 1shot 測定 API

### meas_one_shot()

指定した測定条件で 1 回だけ測定する。

```python
result = dmm.meas_one_shot(
    kind="voltage_dc",
    range_value="AUTO",
    rate="F",
)
```

内部処理

1. running を確認する。
2. 測定中なら `DeviceBusyError` を返す。
3. `CONFigure:*` で測定モードを設定する。
4. `SENSe:RATE` を設定する。
5. host 側開始時刻を記録する。
6. `MEAS1?` を実行する。
7. host 側終了時刻を記録する。
8. 結果を返す。

戻り値

```python
{
    "kind": "voltage_dc",
    "range": "AUTO",
    "rate": "F",
    "value": 1.234,
    "host_time_start": 1710000000.000,
    "host_time_end": 1710000000.025,
    "elapsed": 0.025,
}
```

---

### meas()

`meas_one_shot()` の短縮 API である。

```python
value = dmm.meas("voltage_dc")
```

ただし、戻り値を単なる float にするか、
`meas_one_shot()` と同じ dict にするかは実装時に固定する。
サーバー経由で使うことを考えると、
dict を返す方が望ましい。

---

## continuous 測定 API

### start_continuous_meas()

指定時間、疑似連続測定を開始する。

```python
dmm.start_continuous_meas(
    kind="voltage_dc",
    duration=10.0,
    range_value="AUTO",
    rate="F",
    interval=0.0,
)
```

内部処理

1. 親プロセスが running を確認する。
2. running=True なら `DeviceBusyError` を返す。
3. command queue に continuous 開始命令を送る。
4. worker process が state を running=True にする。
5. worker process が測定モードを設定する。
6. worker process が `duration` 秒間 `MEAS1?` を繰り返す。
7. 各測定値に host 時刻を付ける。
8. 終了後 result store に保存する。
9. state を finished にする。

---

### interval

`interval=0.0` の場合、
worker process は可能な限り速く `MEAS1?` を繰り返す。
`interval>0.0` の場合、
各測定後に指定秒数待つ。
ただし、これは厳密なリアルタイム周期ではない。
取得時刻は host 側時刻で記録する。

---

### continuous 測定中の挙動

continuous 測定中は

```python
running = True
```

となる。

この間、

測定開始や測定条件変更は拒否する。

一方で

```python
get_state()
stop_job()
get_continuous_result()
```

は呼べる。

ただし、`get_continuous_result()` は測定終了後に確定値を返す設計とする。

測定中に途中経過を返すかどうかは別 API として設計する。

---

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
