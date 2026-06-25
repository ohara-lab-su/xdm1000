# XDM1000 ctrl sync test samples

このディレクトリは、現在の `Xdm1000Ctrl` API を sync クライアントから検証するための単純なサンプル群である。

## 前提

・XDM1000 FastAPI サーバーが起動済みである。  
・`xdm1000.yml` がクライアント実行ディレクトリに存在する。  
・クライアントは `DeviceProxy("Xdm1000Ctrl", config="xdm1000.yml", async_mode=False)` を使う。  
・async クライアントは対象外である。  

## API 対応

現在の公開 API は以下である。

・`get_state()`  
・`is_running()`  
・`idn()`  
・`set_mode(mode)`  
・`set_range(range_value)`  
・`set_auto_range(enabled)`  
・`set_integration_speed(speed)`  
・`set_continue_interval(interval)`  
・`set_continue_duration(duration)`  
・`set_continue_count(count)`  
・`meas(wait=None)`  
・`meas_continue(wait=None)`  
・`get_result(clear=False)`  
・`wait_until_done(poll_interval=0.2)`  

`close()` / `disconnect()` は ctrl クラスには存在するが、現在の FastAPI spec には公開されていない。
そのため DeviceProxy 経由のテスト対象には含めない。

## 測定レンジ

測定レンジはハードウェア仕様と SCPI manual の制約を受ける。
サンプルでは安全に実行しやすい電圧・抵抗・容量を中心にしている。

電流測定は端子・結線・ヒューズの扱いを間違えると危険である。
`client_18_current_dc_range_sweep_guarded.py` と
`client_19_current_ac_range_sweep_guarded.py` は、ファイル内の
`RUN_CURRENT_TESTS = True` に変更しない限り実測しない。

## 実行例

```bash
python client_01_idn_and_state.py
python client_02_voltage_dc_auto_single.py
python client_03_voltage_dc_manual_range_sweep.py
python client_12_continue_count_voltage_dc.py
```

## 注意

これらは単体試験フレームワークではなく、実機に対して機能を確認するための単純な検証サンプルである。
装置入力に接続している信号が、設定したレンジの安全範囲内にあることを確認してから実行する。
