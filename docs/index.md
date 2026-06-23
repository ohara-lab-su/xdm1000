# OWON XDM1000/XDM1241 制御ライブラリ
view on [github](https://github.com/ohara-lab-su/xdm1000) / [ohara-lab-su (doc)](https://ohara-lab-su.github.io/)

---
```{toctree}
:maxdepth: 2
:caption: Contents:

man/architecture
man/design_policy
man/scpi_layer_overview
man/scpi_policy
man/control_layer
man/fastapi_layer
man/scpi_api_reference
man/ctrl_api_reference
man/implementation_notes
```
---

OWON XDM1000/XDM1241 用制御ライブラリおよび FastAPI サーバー構成のドキュメントである。

## 構成

- [システム構成](architecture.md)
- [FastAPI 公開レイヤ](fastapi_layer.md)
- [設計方針](design_policy.md)
- [SCPI 採用方針](scpi_policy.md)
- [SCPI ドライバ層の概要](scpi_layer_overview.md)
- [上位制御層](control_layer.md)
- [SCPI ドライバ API リファレンス](scpi_api_reference.md)
- [ctrl API リファレンス](ctrl_api_reference.md)
- [実装時の注意](implementation_notes.md)

## 推奨読順

1. `architecture.md`
2. `design_policy.md`
3. `scpi_policy.md`
4. `control_layer.md`
5. `scpi_api_reference.md`
6. `ctrl_api_reference.md`
7. `fastapi_layer.md`
8. `implementation_notes.md`


---
## 作者
- Kengo NAKADA