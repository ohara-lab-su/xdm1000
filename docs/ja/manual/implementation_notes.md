[![en](https://img.shields.io/badge/lang-en-red.svg)](https://ohara-lab-su.github.io/xdm1000/en/manual/implementation_notes.html) [![ja](https://img.shields.io/badge/lang-ja-blue.svg)](https://ohara-lab-su.github.io/xdm1000/ja/manual/implementation_notes.html)

> **版に関する注意**：本資料の statistics mode に関する記述は旧実装の検討事項です。現行APIとして記載された `Xdm1000Ctrl` には `start_statistics_mode()` が存在しないため、現行の使用方法として解釈しないでください。


# 実装上の注意事項

## ctrl 層に公開しない API

`Xdm1000Ctrl` には `remote()`、`local()`、`query()`、`write()` を公開しない。これらは `Xdm1000Scpi` の低レベル API である。

## running 中の API 制限

長時間測定中の測定・設定 API は command queue に積まず、親側で即時拒否する。状態取得、結果取得、停止要求は running 中でも許可する。

## stop の扱い

停止要求は command queue ではなく stop event / direct 停止フラグで伝える。停止は即時割り込みではなく、測定ループが停止要求を確認した時点で反映される。

## continuous 測定の時刻

continuous 測定の時刻は装置時刻ではなく host 側時刻である。`host_time_*` は `time.time()`、`read_elapsed` と `t_rel_*` は `time.perf_counter()` に基づく。

## statistics mode の注意

`use_process=True` の statistics mode は `CALCulate:AVERage:ALL?` を使う。装置側 statistics の clear/start 条件が未確認であるため、`duration` 秒の厳密な時間窓平均としては扱わない。

`use_process=False` の statistics mode は host 側で `MEAS1?` の値を集め、Python 側で最小・最大・平均を計算する。process 使用時と結果生成方法が異なる。

## RATE 値の不一致

SCPI 層の docstring では `F`、`M`、`L`、ctrl 層では `F`、`M`、`S` という表記が混在している。現状の実装は値検証を行わず、指定された `rate` をそのまま `RATE` に渡す。最終的な正規値は装置マニュアルと実機応答で確認する必要がある。

## Config の SERVER_HOST / SERVER_IP

`Config` の既定属性と YAML 例には `SERVER_HOST` がある。一方、`SyncXdm1000Client` と `AsyncXdm1000Client` は config から `SERVER_IP` を参照する。現状のコードに合わせる場合、client へは `server_ip` を明示するか、`SERVER_IP` 属性を持つ config を渡す必要がある。

## Config のパス解決

`Config` は相対 YAML パスを呼び出し元ファイル基準で解決する。コンストラクタ呼び出しと classmethod `load_yaml()` では `inspect.stack()` の depth が異なる。
