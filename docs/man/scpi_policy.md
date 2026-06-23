# SCPI 採用方針

SCPI ドライバ層では、Programming Manual に記載されている SCPI コマンドを可能な限りそのまま公開する。

上位制御層では、SCPI の存在を利用者に意識させない API を提供する。

上位層では測定器として自然な API を提供することを目的とし、SCPI コマンド体系は隠蔽する。

SCPI は削らない。

上位層で現在利用しない SCPI コマンドであっても、低レベル API として実装する。

---

## CONFigure

CONFigure 系コマンドは測定モードの切り替えを行う。

代表例

- CONFigure:VOLTage:DC
- CONFigure:VOLTage:AC
- CONFigure:CURRent:DC
- CONFigure:CURRent:AC
- CONFigure:RESistance
- CONFigure:FRESistance
- CONFigure:FREQuency
- CONFigure:PERiod
- CONFigure:CAPacitance
- CONFigure:TEMPerature:RTD
- CONFigure:DIODe
- CONFigure:CONTinuity

SCPI 層では個別メソッドとして提供する。

ctrl 層では

```python
set_meas_mode(
    kind="voltage_dc",
    range_value="AUTO",
    rate="F",
)
```

へ集約する。

---

## SENSe

SENSe 系では測定条件を設定する。

代表的なものは

- Rate
- Range
- Auto Range
- Null
- dB
- dBm

である。

Rate は

- F
- M
- S

の3段階であり、
これは装置内部の測定速度であって、
continuous 測定で指定する polling interval とは意味が異なる。

---

## MEAS 系コマンド

Programming Manual では測定値取得として少なくとも次が提供される。

```
MEAS?
MEAS1?
MEAS2?
```

これらは用途が異なる。

---

## MEAS?

汎用測定値取得コマンドである。
現在の表示状態に応じた測定値を返す。
表示モードによって戻り値の構造が変わる可能性があるため、
ctrl 層では標準 API として採用しない。
SCPI 層では

```python
meas()
```

として公開する。

---

## MEAS1?

メイン表示値取得である。
ctrl 層では
主測定値
として採用する。
理由

- 常に単一値として扱える
- API の戻り値を固定できる
- continuous 測定を単純な時系列として保存できる

1shot
continuous
ともに MEAS1? を使用する。

---

## MEAS2?

サブ表示取得である。

SCPI 層では

```python
meas_sub()
```

として提供する。
ctrl 層では現在は公開しない。
サブ表示の意味は測定モードに依存するため、
将来必要になった段階で専用 API として設計する。

---

## CALCulate

CALCulate は測定コマンドではなく、
測定値に対する演算機能である。

代表例

- CALCulate:FUNCtion
- CALCulate:AVERage:MINimum?
- CALCulate:AVERage:MAXimum?
- CALCulate:AVERage:AVERage?
- CALCulate:AVERage:ALL?

CALCulate:AVERage:ALL? は

- minimum
- maximum
- average
- count

を返す。

これは時間指定平均ではない。
Statistics 機能である。
Statistics の開始条件・終了条件・リセット条件については Programming Manual の記述だけでは仕様が確定できないため、
ctrl 層では
Statistics Mode
というテスト機能として実装する。
時間窓平均としては扱わない。

---
