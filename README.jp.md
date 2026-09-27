# ComfyUI-DLSS5-AMD · Experimental Bridge

[English](README.md) | [日本語](README.jp.md)

> **セットアップの推奨:** 導入には手作業が多いため、Codex などのコーディングエージェントに[個人利用の導入手順](docs/PERSONAL_SETUP.md)を読ませ、自分の PC でのセットアップ・検査・エラー対応を任せることを強く推奨します。正当に入手した `nvngx_dlssnr.dll` の用意と、外部ランタイムのライセンス確認は利用者自身で行ってください。

**実験版 v0.1.0a1 · 検証記録の更新: 2026-09-27**

Windows / RX 9070 XT 向けの、ローカルでビルドする外部 AMD Neural Rendering ホストを ComfyUI に接続する実験的カスタムノードです。**2026-09-26 に実ニューラル処理を、2026-09-27 に AMD AMF VideoSR1.1 による統合画像・3フレーム動画の拡大を ComfyUI API で確認しました。** DLSS の重み・DLL・ビルド済み GPU ホストは含みません。新規 PC での導入再現、自然画像の画質、長い動画は未検証です。

これは NVIDIA / AMD の公式製品ではありません。名称中の DLSS は対象技術の識別用です。NVIDIA / AMD との提携・推奨を示しません。

[初回 2026-09-25 の調査レポート（オフライン HTML）](REPORT.html)

## はじめかた（個人利用）

1. Windows x64、RX 9070 XT、動作する ComfyUI を用意します。初回のホストビルドには、Git・CMake・MSVC・NMake・Windows SDK が使える **x64 Visual Studio Developer PowerShell** が必要です。利用権限のある `nvngx_dlssnr.dll` **310.8.0.0**、またはその DLL が1個入った ZIP を用意します。画像・動画の統合拡大には `sr_amf` と AMF hardware acceleration に対応する Windows 用 `ffmpeg.exe` も必要です。[配布元と利用条件](docs/PERSONAL_SETUP.md)および[外部ランタイムの LICENSE](https://github.com/danielblnc/DLSS-NR-on-AMD/blob/v0.2.17/LICENSE)を確認してください。
2. **実際の** ComfyUI の `custom_nodes` に clone します。以下のパスは例です。`$Py` は ComfyUI が使う Python に合わせてください。

   ```powershell
   $Comfy = 'C:\path\to\ComfyUI'
   $Py = 'C:\path\to\ComfyUI\.venv\Scripts\python.exe'
   $OwnedZip = 'C:\path\to\your-owned-files.zip'
   $AmfFfmpeg = 'C:\path\to\AMF-enabled\ffmpeg.exe'
   Set-Location (Join-Path $Comfy 'custom_nodes')
   git clone https://github.com/ELRdn/ComfyUI-DLSS5-AMD.git
   Set-Location .\ComfyUI-DLSS5-AMD
   & .\scripts\setup_personal.ps1 -Python $Py -ModelZip $OwnedZip -FFmpeg $AmfFfmpeg -AcceptRuntimeLicense
   ```

   ZIP ではなく DLL 単体なら `-ModelZip` を `-ModelDll 'C:\path\to\nvngx_dlssnr.dll'` に置き換えます。スクリプトは既存設定を上書きしません。ハッシュの検査は新しい PC での GPU 推論や画質の合格ではありません。ビルド、HIP 番号、AMF の検査で止まる場合は[詳細手順](docs/PERSONAL_SETUP.md)を参照してください。
3. ComfyUI を再起動します。画像は小さな **SDR/sRGB** ファイルを ComfyUI の `input` に置くか Load Image からアップロードします。[06 のワークフロー](workflows/06_nr_amf_image_ONE_NODE_EXPERIMENTAL.json)を開き、Load Image でその画像を選び、`factor=2` から実行します。Save Image が ComfyUI の出力フォルダーへ保存します。動画は短い **SDR/CFR** ファイルを ComfyUI の `input` 直下へ置き、[07 のワークフロー](workflows/07_nr_amf_video_ONE_NODE_EXPERIMENTAL.json)でファイル名を選び、`max_frames` を素材のフレーム数以上にして実行します。可逆 MKV は `output/amd_nr/` に保存され、ノードもパスを返します。動画プレーヤー UI はありません。

06/07 は**元の寸法で NR を処理し、後段の AMD AMF VideoSR1.1 で拡大**します。外部の ComfyUI AMD Video Upscaler ノードは不要です。UI JSON の構造検査と、対応する API グラフの実行を確認しました。06/07 のブラウザーからの手動実行は未確認です。この導入は個人・非商用の研究用途であり、製品画質や商用利用を保証する公開版ではありません。

## まず読む

| 目的 | ファイル |
|---|---|
| clone、必要ファイル、配布元のリンク | [docs/PERSONAL_SETUP.md](docs/PERSONAL_SETUP.md) |
| 初回 2026-09-25 の調査記録 | [REPORT_ja.md](REPORT_ja.md) |
| 完了条件つきロードマップ | [ROADMAP.md](ROADMAP.md) |
| Windows / ComfyUI への導入 | [docs/WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md) |
| ランタイムの入手・導入・補助ツール | [docs/RUNTIME_SETUP_ja.md](docs/RUNTIME_SETUP_ja.md) |
| 検証範囲と初回 2026-09-25 のテスト記録 | [docs/TESTING.md](docs/TESTING.md)、[evidence/test-summary.json](evidence/test-summary.json) |
| 次の開発エージェントへの引き継ぎ | [docs/HANDOFF.md](docs/HANDOFF.md) |

## このリポジトリで実装したもの

ComfyUI の IMAGE を検査し、RGBA8 ファイルとして外部ネイティブホストへ渡し、完了レポートと出力サイズを確認して IMAGE に戻す経路です。失敗したとき、普通の拡大処理や入力コピーを DLSS の成功として返しません。

| ノード | 動作 |
|---|---|
| `AMDNRSettings` | 出力合成の mix。モデル内部の強度・拡大率ではありません |
| `AMDNRApply` | 実験的ネイティブ接続。実行ファイルと DLL の事前設定が必要 |
| `AMDNRRenderUpscale` | 画像1ノードで同寸法の NR → 別工程の AMD AMF VideoSR1.1 による2～8倍拡大 |
| `AMDNRRoundtrip` | CPU の入出力診断専用。**DLSS ではありません** |
| `AMDNRResize` | 通常の bicubic 拡大。**DLSS / FSR ではありません** |
| `AMDNRCompare` | 元画像と結果の左右比較・画素差。画質スコアではありません |
| `AMDNRDiagnostics` | Python / PyTorch / FFmpeg / 設定の診断。DLL はロードしません |
| `AMDNRVideoFile` | 入力フォルダーの短い SDR/CFR 動画を処理し、可逆 FFV1/MKV を出力 |
| `AMDNRVideoUpscaleFile` | 動画1ノードで各フレームの NR → VideoSR1.1。音声コピー付き可逆 MKV を出力 |

フレーム数、ハッシュ、実行時間、失敗理由を JSON に残します。動画は RAM 使用量をチャンク単位に制限しますが、ディスク上には動画全体の中間データを置きます。フルムービー向けストリーミング実装ではありません。

## 実装・検証の境界

**実装済み:** Python ノード、CLI、外部ホスト接続、設定・SHA-256 検査、画像／動画処理、タイムアウト、キャンセル、上書き防止、テスト、サンプルワークフロー。

**CPU で検証済み:** ノードの import・メソッド、画像の往復、明示的なテストダブルを使ったネイティブ入出力契約、実 FFmpeg による画素／フレーム順序／音声ペイロードの往復。

**Windows 実機確認（2026-09-26）:** 固定ホストと v0.2.17 ランタイムで、RX 9070 XT 上の異なる 640×360 SDR 画像 2 枚、CLI、実 ComfyUI のニューラル処理が成功しました。ComfyUI API から単体 PNG と左右比較画像を保存しました。検証したローカル設定は `fast_isolated=true`。通常の待機設定では画像回収条件を満たせず、検査条件は変更していません。[検証記録](docs/RX9070XT_VALIDATION_2026-09-26.md)を参照。

**未検証:** 画質改善、自然写真での品質、持続的な動画処理、一般的な性能、VRAM 最大使用量。合成画像と3フレーム動画で確認したのは、実処理、出力寸法、ファイル・音声の経路です。

## GPU 不要の確認

リポジトリ直下で、既存の適切な Python 環境から実行します。

```powershell
python -m amd_nr doctor
python -m amd_nr selftest --output selftest-output
```

`selftest-output/reference_NOT_DLSS.png` は入出力確認用です。ニューラル処理結果ではありません。

開発用テストは次のとおりです。**ComfyUI の GPU 用 PyTorch を CPU 版で上書きしないでください。** 本リポジトリの requirements は PyTorch をインストールしません。

```powershell
python -m pip install -r requirements.txt
python -m pip install pytest coverage
python scripts/collect_evidence.py
```

ノードのメソッドテストには既存の PyTorch が必要です。ComfyUI が利用する Python と、端末の `python` が一致しているか確認してください。

## ネイティブ版の導入

[個人利用の一括導入](docs/PERSONAL_SETUP.md)は作者公開の固定 **v0.2.17** セットアップを取得し、固定ホストをローカルでビルドし、ハッシュを検査して非公開設定を作ります。NVIDIA NR DLL はダウンロードしません。工程別の[Windows 手動手順](docs/WINDOWS_SETUP.md)と[ランタイム調査](docs/RUNTIME_SETUP_ja.md)も参照してください。ROCm、作者の AMD 向け NR ランタイム、AMF VideoSR1.1 は別物で、ROCm だけでは NR 用プロキシ・重み・NVIDIA DLL はそろいません。本リポジトリの MIT と、外部ランタイム・モデルの利用条件も別です。

## ComfyUI

このフォルダー全体を `ComfyUI/custom_nodes/ComfyUI-DLSS5-AMD/` に配置して再起動します。

- `workflows/01_cpu_transport_NOT_DLSS.json`: CPU 診断。
- `workflows/02_native_image_EXPERIMENTAL.json`: ネイティブ処理と A/B 比較。
- `workflows/03_native_video_EXPERIMENTAL.json`: 短い動画のファイル処理。
- `workflows/04_rx9070xt_native_validation_EXPERIMENTAL.json`: 診断付きネイティブ画像検証。640×360 SDR で実行確認済み。ローカルランタイムが必要です。
- `workflows/05_rx9070xt_nr_then_amf_sr_EXPERIMENTAL.json`: NR の後に**別の AMD AMF VideoSR1.1**ノードをつなぐ 2 倍の例。外部の ComfyUI AMD Video Upscaler と AMF 対応 FFmpeg が必要です。[倍率検証記録](docs/SCALING_VALIDATION_2026-09-27.md)を参照。
- `workflows/06_nr_amf_image_ONE_NODE_EXPERIMENTAL.json`: このカスタムノード内の1ノードで画像の NR と VideoSR1.1 拡大。
- `workflows/07_nr_amf_video_ONE_NODE_EXPERIMENTAL.json`: 短い SDR/CFR 動画を1ノードで処理し、音声をコピー。

同名の `.api.json` は API 用のグラフ形式です。通常の UI には `.api` の付かない JSON を読み込み、Load Image の画像／動画ファイルを選び直してください。04 はブラウザーで実行済み、05～07 は ComfyUI API で実行し、UI 形式を構造検査済みです。06/07 では、AMF 対応 FFmpeg をサーバー側の非公開設定に `python scripts/setup_runtime.py configure-amf --ffmpeg C:\path\to\ffmpeg.exe --config config\backend.local.json` で固定してから ComfyUI を再起動します。[Windows 導入ガイド](docs/WINDOWS_SETUP.md)を参照。

## 大切な制限

NR 段階は **SDR、RGBA8 転送、時間方向の履歴なし、サイズ維持**です。既定の入力許容範囲は幅 1920・高さ 1080 以下、偶数かつ 16 以上。統合ノードは NR の後にだけ拡大し、出力の各辺を 8192 以下に制限します。縦長の高さ 1280 画像や 4K 入力を NR 前に自動縮小しません。

Load Image の MASK は透明度由来で反転されている場合があります。本ノードの effect_mask は「白＝効果を適用」です。意味を確認せずに直結しないでください。

拡大は 06/07 の内部で NR の後段に AMF VideoSR1.1 を実行します。RX 9070 XT と合成画像では 640×360 起点の8倍、1920×1080 起点の4倍まで短時間の試験に成功し、統合した画像・3フレーム動画経路も2倍で成功しました。これは実用画質の上限や DLSS 超解像の実装を意味しません。`AMDNRResize` は bicubic の対照用です。FSR4 は実装していません。

## ライセンス・プライバシー

本リポジトリのオリジナルコードは MIT。外部ランタイム、重み、NVIDIA DLL、他プロジェクトのライセンスは別です。コードの MIT 表示はモデル配布権を与えません。`LICENSE`、`THIRD_PARTY_NOTICES.md`、`SECURITY.md` を参照。

通常実行でネットワーク送信はしません。ログにはローカルパスが入る可能性があります。`--keep-debug-files` は画像／DLL／重みのコピーを残すため、公開・アップロードしないでください。
