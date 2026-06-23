# FastAPI 公開レイヤ

`server_fastapi/` は、

ローカル制御層を FastAPI / ese774_frame で公開するための別レイヤである。

`xdm1000_ctrl.py` 自体は FastAPI に依存しない。

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
- set_meas_mode()
- meas_one_shot()
- start_continuous_meas()
- start_statistics_mode()

公開しないもの

- remote()
- local()
- raw SCPI
- query()
- write()

---
