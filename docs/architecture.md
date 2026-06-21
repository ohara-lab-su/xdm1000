# アーキテクチャ

## 設計目的

本ライブラリは OWON XDM1000 シリーズデジタルマルチメータを Python から制御することを目的とする。

設計では次の事項を重視している。

- ローカル制御を第一とする。
- FastAPI に依存しない。
- SCPI を低レベルへ閉じ込める。
- 測定器として扱う API を提供する。
- multiprocessing を利用した長時間測定を行う。

FastAPI や ese774_frame は上位の利用形態であり、本ライブラリ自身はそれらへ依存しない。

---

# レイヤ構造

ライブラリは三層構造とする。

```text
Application
      │
      ▼
Xdm1000Ctrl
      │
      ▼
Xdm1000Scpi
      │
      ▼
XDM1000
```

## Xdm1000Scpi

SCPI を 1 対 1 に対応付ける低レベルドライバである。

責務は

- SCPI コマンド送信
- SCPI 応答取得

のみである。

測定シーケンスは持たない。

---

## Xdm1000Ctrl

測定器として扱うための上位制御クラスである。

責務は

- 測定モード設定
- One Shot
- Continuous
- Statistics
- 状態管理
- Worker 管理

である。

利用者は通常こちらのみ利用する。

---

## Worker

長時間測定専用プロセスである。

SCPI の詳細を知らず、

```
測定開始
↓
測定実行
↓
結果保存
↓
終了通知
```

のみを担当する。

---

# プロセスモデル

```
          Xdm1000Ctrl

     ┌──────────────┐
     │   Parent     │
     └──────────────┘
             │
      Command Queue
             │
             ▼
     ┌──────────────┐
     │    Worker    │
     └──────────────┘
             │
     Response Queue
             │
             ▼
          Xdm1000Ctrl
```

Parent が API を管理する。

Worker は測定のみ担当する。

---

# Parent の責務

Parent は

- running
- state
- Queue
- Result

のみ保持する。

SCPI を直接実行しない。

---

# Worker の責務

Worker は

- SCPI
- 長時間測定
- stop_event

のみ扱う。

running は Parent が管理する。

---

# Running

長時間測定中は

```
running=True
```

となる。

この間は

- 新しい測定開始
- 測定条件変更

を拒否する。

一方、

- state
- running
- stop
- result

のみ実行可能である。

---

# 状態遷移

```
Idle
↓
Running
↓
Finished
↓
Idle
```

エラー時

```
Running
↓
Error
↓
Idle
```

停止要求時

```
Running
↓
Stopped
↓
Idle
```

---

# 測定モード

本ライブラリでは三種類の測定モードを提供する。

- One Shot
- Continuous
- Statistics

これらは SCPI の概念ではなく、Xdm1000Ctrl が提供する上位機能である。