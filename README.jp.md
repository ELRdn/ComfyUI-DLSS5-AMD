# ComfyUI-DLSS5-AMD · Experimental Bridge

[English](README.md) | [日本語](README.jp.md)

**Version 0.1.0a1 · Research snapshot: 2026-09-25**

Windows / RX 9070 XT 向けの、ユーザーが用意した AMD Neural Rendering ホストを ComfyUI に接続する実験的カスタムノードです。**2026-09-26 に実ニューラル処理を、2026-09-27 に AMD AMF VideoSR1.1 による統合画像・3フレーム動画の拡大を ComfyUI API で確認しました。** DLSS の重み・DLL・完成済み GPU エンジンは含みません。

これは NVIDIA / AMD の公式製品ではありません。名称中の DLSS は対象技術の識別用です。NVIDIA / AMD との提携・推奨を示しません。

[ブラウザー用の総合レポート（オフライン HTML）](REPORT.html)

## まず読む

| 目的 | ファイル |
|---|---|
| 調査結果と技術判断 | [REPORT_ja.md](REPORT_ja.md) |
| 完了条件つきロードマップ | [ROADMAP.md](ROADMAP.md) |
| Windows / ComfyUI への導入 | [docs/WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md) |
| ランタイムの入手・導入・補助ツール | [docs/RUNTIME_SETUP_ja.md](docs/RUNTIME_SETUP_ja.md) |
| テスト結果と未検証項目 | [evidence/test-summary.json](evidence/test-summary.json)、[docs/TESTING.md](docs/TESTING.md) |
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

個人利用で Git clone から導入する場合は [ZIP 対応セットアップ](docs/PERSONAL_SETUP.md) を使えます。正当に入手した `nvngx_dlssnr.dll` を含む ZIP（または DLL 単体）を指定すると、固定した作者公開セットアップの取得、ホストのビルド、生成物検証、ComfyUI の非公開設定まで順に実行します。統合画像・動画拡大には AMF 対応 FFmpeg も指定できます。外部ランタイムは非商用・再配布禁止のため、有料の一般客向け提供には作者から別途許諾が必要です。

ROCm、作者の AMD 向け NR ランタイム、AMF VideoSR1.1 は別物です。ROCm だけでは NR 用のプロキシ・重み・NVIDIA DLL はそろいません。06/07 はこのカスタムノード内で FFmpeg の AMF フィルターを呼ぶため、外部の ComfyUI AMD Video Upscaler ノードは不要です。配布元リンクと本人が用意するファイルは[導入ガイド](docs/PERSONAL_SETUP.md)にまとめています。

[Windows 手順](docs/WINDOWS_SETUP.md)に従い、固定リビジョンの外部ホストを取得・確認・ビルドし、正当な利用権限のあるローカルランタイムを設定します。外部ホストのコードも実行前に確認してください。

```powershell
python scripts/fetch_upstream.py
# 続いて x64 Visual Studio Developer PowerShell で:
.\scripts\build_native.ps1 -Python python
```

これは **ホストのビルドまで**です。重み／ランタイム取得やドライバー変更は行いません。実行用設定は `init-config` でハッシュを生成後、人間が確認して有効化します。詳細は手順書参照。

別途、公式 **v0.2.17** セットアップを取得して SHA-256 を照合する補助ツールを用意しています。

```powershell
python scripts/setup_runtime.py prepare
python scripts/setup_runtime.py status
```

導入には、利用者の正当に入手した **`nvngx_dlssnr.dll` 310.8.0.0（x64）** が必要です。AMD セットアップがプロキシと重みをローカルに生成し、補助ツールが固定ハッシュを確認して設定を作成します。HIP 番号と `install` コマンドは [導入ガイド](docs/RUNTIME_SETUP_ja.md) を参照。AMD ランタイムは個人・非商用利用限定で、再配布は禁止されています。最新版とこのホストの互換性は未検証です。

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
