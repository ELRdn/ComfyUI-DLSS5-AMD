# 一次資料と出所

確認日: **2026-09-25**。GitHub はファイル本体／API を取得し、検索インデックスの説明だけで実装を決定していない。モデルやバイナリはダウンロードしていない。資料の記述は作者の主張を含み、手元での独立した GPU 再現とは別。

| ID | 一次資料 | 本レポートでの使用範囲 |
|---|---|---|
| S01 | [NVIDIA — DLSS 5 3D-Guided Neural Rendering](https://www.nvidia.com/en-gb/geforce/news/dlss-5-3d-guided-neural-rendering/) / 2026-09-01。補足: [公式発表](https://nvidianews.nvidia.com/news/nvidia-dlss-5-delivers-ai-powered-breakthrough-in-visual-fidelity-for-games) / 2026-03-16 | NR の位置づけ、SR 等との独立性、ゲーム由来 motion vectors。公式の品質表現は独立検証結果として扱わない |
| S02 | [eikkapine/DLSS5-AMD-Video README](https://github.com/eikkapine/DLSS5-AMD-Video/blob/9303dfaa14c2ca83e237ff18318bdfc0b767f6fb/README.md) | 実験的な動画ホスト、作者の 120 フレーム・408.98 秒の測定、外部アセット分離 |
| S03 | [native/README.md](https://github.com/eikkapine/DLSS5-AMD-Video/blob/9303dfaa14c2ca83e237ff18318bdfc0b767f6fb/native/README.md) / [enhance.py](https://github.com/eikkapine/DLSS5-AMD-Video/blob/9303dfaa14c2ca83e237ff18318bdfc0b767f6fb/enhance.py) | RGBA8、CLI、完了レポート、フレーム分離、color-only INI、fast opt-in |
| S04 | [native/CMakeLists.txt](https://github.com/eikkapine/DLSS5-AMD-Video/blob/9303dfaa14c2ca83e237ff18318bdfc0b767f6fb/native/CMakeLists.txt) / [native/src/main.cpp](https://github.com/eikkapine/DLSS5-AMD-Video/blob/9303dfaa14c2ca83e237ff18318bdfc0b767f6fb/native/src/main.cpp) / [LICENSE](https://github.com/eikkapine/DLSS5-AMD-Video/blob/9303dfaa14c2ca83e237ff18318bdfc0b767f6fb/LICENSE) | ビルド依存、native ソース冒頭の CLI/report 実装、プロジェクト固有コードと第三者素材の権利分離 |
| S05 | [lmxxf/dlss5-on-amd-9070xt-porting README](https://github.com/lmxxf/dlss5-on-amd-9070xt-porting/blob/main/README.md) | 取得時の 0.30 / 2026-09-25、HIP/D3D12 統合、ゲーム NR→FSR、配布物とソースの差異。mutable main の調査スナップショット |
| S06 | [include/LmxxfNrApi.h](https://github.com/lmxxf/dlss5-on-amd-9070xt-porting/blob/main/include/LmxxfNrApi.h) / [LICENSE](https://github.com/lmxxf/dlss5-on-amd-9070xt-porting/blob/main/LICENSE) | D3D12 の device/queue/resource を渡す C ABI、capabilities、MIT の範囲。ヘッダーだけで本体の完全動作を保証しない |
| S07 | [danielblnc/DLSS-NR-on-AMD README](https://github.com/danielblnc/DLSS-NR-on-AMD/blob/master/README.md) / [ComfyUI 対応要望 #105](https://github.com/danielblnc/DLSS-NR-on-AMD/issues/105) | 外部 AMD ランタイムとゲーム統合。Issue の存在を、他の完成品が一切ないことの証拠には使わない |
| S08 | [taowen/dlss5-onnx model card](https://huggingface.co/taowen/dlss5-onnx) / [DLSS5_AMD.md](https://huggingface.co/taowen/dlss5-onnx/blob/main/docs/DLSS5_AMD.md) | 固定 256×256、linear RGB、静止画再構成、Linux/890M の限定された検証。Windows/9070 XT の保証ではない |
| S09 | [ComfyUI — Images, Latents, and Masks](https://docs.comfy.org/custom-nodes/backend/images_and_masks) / [Properties](https://docs.comfy.org/custom-nodes/backend/server_overview) / [Lifecycle](https://docs.comfy.org/custom-nodes/backend/lifecycle) | IMAGE/MASK の形状、LoadImage の反転 alpha、classic ノード公開方式 |
| S10 | [GPUOpen — FSR 3.1.4 Upscaler](https://gpuopen.com/manuals/fidelityfx_sdk/techniques/super-resolution-upscaler/) | temporal SR の補助入力を検討する根拠。FSR4 のすべての API/モードへ一般化しない |
| S11 | [Blueforcer/ComfyUI-DLSS5-Enhancer README](https://github.com/Blueforcer/ComfyUI-DLSS5-Enhancer/blob/main/README.md) | NVIDIA 向け NGX/D3D12 外部ワーカー、ComfyUI V3、外部バイナリを別管理する設計 |

## 取得した主な Git blob ID

Git blob ID はファイル内容の Git 上の識別子であり、ファイル単体 SHA-256 とは異なる。実行用 EXE/DLL は別途 SHA-256 を計算する。

| ファイル | 取得時の blob ID |
|---|---|
| eikkapine README | `c63f9c56d59d042ea46a5c12fd90b91fb480ccd1` |
| eikkapine enhance.py | `ce070c91013eed3818e9e18a5141fb604bd6fce6` |
| eikkapine native README | `c6a73af3dba9346399af45c50e63837441157320` |
| eikkapine native CMake | `4bcb94adc71f792e40072c425400fa99ed305166` |
| eikkapine native main.cpp | `74e482a1913e9482033b68e447d2851b293d0c48` |
| eikkapine LICENSE | `3d27b4a1d9ea52e274a39eb7764d67d68265c147` |
| lmxxf C ABI header | `b2dafec6da0cc7bdc61102ea530d21e0c5c8c0d4` |
| lmxxf LICENSE | `ea85db659577a0c8d6fec74c70aea54c30225120` |
| danielblnc README | `3cb788e61b69763dac6430c22e59f14ec97b8802` |
| Blueforcer README | `2efd3601ac8a648bcb1e03270fa1905cf5daa4cb` |

## 確認範囲の限界

初回調査は公開 README とコード契約を対象とし、すべての upstream コードを監査したという意味ではない。外部ホストのローカルビルドと実行は下記の追加検証で行った。取得できなかったページや前回答の性能値は、実装の確定根拠から除外した。

初回調査環境では一般の GitHub clone がネットワーク解決に失敗したため、公開資料は GitHub コネクター／Web から読んだ。**2026-09-26 の追記:** ユーザー環境では固定ソースの取得・ハッシュ照合、Windows ビルド、640×360 の実ニューラル処理まで完了した。追加の実行証拠と範囲は [実機検証記録](RX9070XT_VALIDATION_2026-09-26.md) を参照。
