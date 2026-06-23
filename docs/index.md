# XDM1000 / XDM1241 制御ドキュメント

OWON XDM1000/XDM1241 系デジタルマルチメータ用の SCPI ドライバ、上位制御クラス、multiprocessing ワーカー、FastAPI/ese774_frame 透過サーバー構成のドキュメントである。

---
```{toctree}
:maxdepth: 2
:caption: Contents:

api/modules
man/tutorial
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

## 構成

- [チュートリアル](man/tutorial.md)
- [システム構成](man/architecture.md)
- [設計方針](man/design_policy.md)
- [SCPI ドライバ層の概要](man/scpi_layer_overview.md)
- [SCPI 採用方針](man/scpi_policy.md)
- [上位制御層](man/control_layer.md)
- [FastAPI 公開レイヤ](man/fastapi_layer.md)
- [SCPI ドライバ API リファレンス](man/scpi_api_reference.md)
- [ctrl API リファレンス](man/ctrl_api_reference.md)
- [実装上の注意事項](man/implementation_notes.md)

## 推奨読順

1. `architecture.md`
2. `design_policy.md`
3. `scpi_layer_overview.md`
4. `scpi_policy.md`
5. `control_layer.md`
6. `fastapi_layer.md`
7. `scpi_api_reference.md`
8. `ctrl_api_reference.md`
9. `implementation_notes.md`

---
## 作者
- Kengo NAKADA
