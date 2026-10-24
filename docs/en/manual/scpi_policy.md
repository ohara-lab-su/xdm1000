[![en](https://img.shields.io/badge/lang-en-red.svg)](https://ohara-lab-su.github.io/xdm1000/en/manual/scpi_policy.html) [![ja](https://img.shields.io/badge/lang-ja-blue.svg)](https://ohara-lab-su.github.io/xdm1000/ja/manual/scpi_policy.html)

# SCPI Design Policy

The SCPI driver remains a thin mapping of instrument commands to Python methods. Higher-level concepts such as cached mode, range, measurement interval, and worker execution belong to the control layer. `CONFigure:*` remains available in the low-level driver; the controller uses separate function, range, autorange and rate operations. The controller reads the primary display via `MEAS1?`.

> **Documentation scope:** This English guide is an abridged technical companion to the complete Japanese manual. This page is a summary of the supplied Japanese document; consult the Japanese version for details and complete examples.

## SCPI versus controller responsibilities

## Configuration and function/range

```text
FUNCtion "..."    # 測定モード
RANGE <value>     # 測定レンジ
AUTO              # オートレンジ有効化
RATE <F|M|S>      # 内部測定速度
```

## RATE

## Measurement commands
