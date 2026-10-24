[![en](https://img.shields.io/badge/lang-en-red.svg)](https://ohara-lab-su.github.io/xdm1000/en/manual/design_policy.html) [![ja](https://img.shields.io/badge/lang-ja-blue.svg)](https://ohara-lab-su.github.io/xdm1000/ja/manual/design_policy.html)

# Design Policy

The design separates SCPI commands, instrument control, long-running acquisition and FastAPI exposure. `config` values take precedence over constructor arguments for port, baud rate and timeout. In process mode the worker handles serial communication; direct mode executes in the caller process. Repeated instrument settings are cached to avoid redundant SCPI commands.

> **Documentation scope:** This English guide is an abridged technical companion to the complete Japanese manual. This page is a summary of the supplied Japanese document; consult the Japanese version for details and complete examples.

## Basic principles

## Configuration precedence

## Process mode

## Measurement-setting cache

```text
kind        = voltage_dc
range_value = AUTO
rate        = F
```

## Long-running measurements
