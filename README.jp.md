# ComfyUI-DLSS5-AMD · Experimental Bridge

[English](README.md) | [日本語](README.jp.md)

**Version 0.1.0a1 · Research snapshot: 2026-09-25**

Windows / RX 9070 XT 向けの、ユーザーが用意した AMD Neural Rendering ホストを ComfyUI に接続する実験的カスタムノードです。**DLSS の重み・DLL・完成済み GPU エンジンは含みません。今回の開発環境では実 GPU 推論を実行していません。**

これは NVIDIA / AMD の公式製品ではありません。名称中の DLSS は対象技術の識別用です。NVIDIA / AMD との提携・推奨を示しません。

[ブラウザー用の総合レポート（オフライン HTML）](REPORT.html)

## まず読む

| 目的 | ファイル |
|---|---|
| 調査結果と技術判断 | [REPORT_ja.md](REPORT_ja.md) |
| 完了条件つきロードマップ | [ROADMAP.md](ROADMAP.md) |
| Windows / ComfyUI への導入 | [docs/WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md) |
| テスト結果と未検証項目 | [evidence/test-summary.json](evidence/test-summary.json)、[docs/TESTING.md](docs/TESTING.md) |
| 次の開発エージェントへの引き継ぎ | [docs/HANDOFF.md](docs/HANDOFF.md) |

## このリポジトリで実装したもの

ComfyUI の IMAGE を検査し、RGBA8 ファイルとして外部ネイティブホストへ渡し、完了レポートと出力サイズを確認して IMAGE に戻す経路です。失敗したとき、普通の拡大処理や入力コピーを DLSS の成功として返しません。

| ノード | 動作 |
|---|---|
| `AMDNRSettings` | 出力合成の mix。モデル内部の強度・拡大率ではありません |
| `AMDNRApply` | 実験的ネイティブ接続。実行ファイルと DLL の事前設定が必要 |
| `AMDNRRoundtrip` | CPU の入出力診断専用。**DLSS ではありません** |
| `AMDNRResize` | 通常の bicubic 拡大。**DLSS / FSR ではありません** |
| `AMDNRCompare` | 元画像と結果の左右比較・画素差。画質スコアではありません |
| `AMDNRDiagnostics` | Python / PyTorch / FFmpeg / 設定の診断。DLL はロードしません |
| `AMDNRVideoFile` | 入力フォルダーの短い SDR/CFR 動画を処理し、可逆 FFV1/MKV を出力 |

フレーム数、ハッシュ、実行時間、失敗理由を JSON に残します。動画は RAM 使用量をチャンク単位に制限しますが、ディスク上には動画全体の中間データを置きます。フルムービー向けストリーミング実装ではありません。

## 実装・検証の境界

**実装済み:** Python ノード、CLI、外部ホスト接続、設定・SHA-256 検査、画像／動画処理、タイムアウト、キャンセル、上書き防止、テスト、サンプルワークフロー。

**CPU で検証済み:** ノードの import・メソッド、画像の往復、明示的なテストダブルを使ったネイティブ入出力契約、実 FFmpeg による画素／フレーム順序／音声ペイロードの往復。

**未検証:** Windows ネイティブビルド、RX 9070 XT での推論、実際の ComfyUI サーバーとブラウザー上の動作、画質改善、GPU 速度、VRAM 使用量。自動テストの合格は、これらの合格を意味しません。

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

[Windows 手順](docs/WINDOWS_SETUP.md)に従い、固定リビジョンの外部ホストを取得・確認・ビルドし、正当な利用権限のあるローカルランタイムを設定します。外部ホストのコードも実行前に確認してください。

```powershell
python scripts/fetch_upstream.py
# 続いて x64 Visual Studio Developer PowerShell で:
.\scripts\build_native.ps1 -Python python
```

これは **ホストのビルドまで**です。重み／ランタイム取得やドライバー変更は行いません。実行用設定は `init-config` でハッシュを生成後、人間が確認して有効化します。詳細は手順書参照。

## ComfyUI

このフォルダー全体を `ComfyUI/custom_nodes/ComfyUI-DLSS5-AMD/` に配置して再起動します。

- `workflows/01_cpu_transport_NOT_DLSS.json`: CPU 診断。
- `workflows/02_native_image_EXPERIMENTAL.json`: ネイティブ処理と A/B 比較。
- `workflows/03_native_video_EXPERIMENTAL.json`: 短い動画のファイル処理。

同名の `.api.json` は API 用のグラフ形式です。通常の UI には `.api` の付かない JSON を読み込み、Load Image の画像／動画ファイルを選び直してください。これらは構造検査済みですが、ブラウザー上の実行確認は未実施です。

## 大切な制限

初版は **SDR、RGBA8 転送、時間方向の履歴なし、サイズ維持**です。既定ネイティブ許容範囲は幅 1920・高さ 1080 以下、偶数かつ 16 以上です。縦長の高さ 1280 画像や 4K を自動的に縮小しません。明示的な前処理または実機検証後の設定変更が必要です。

Load Image の MASK は透明度由来で反転されている場合があります。本ノードの effect_mask は「白＝効果を適用」です。意味を確認せずに直結しないでください。

真の拡大が目的なら、画質評価を通した NR の後に、利用中の ComfyUI 超解像ノードを別工程として接続します。`AMDNRResize` はあくまで bicubic の対照用です。FSR4 は実装していません。

## ライセンス・プライバシー

本リポジトリのオリジナルコードは MIT。外部ランタイム、重み、NVIDIA DLL、他プロジェクトのライセンスは別です。コードの MIT 表示はモデル配布権を与えません。`LICENSE`、`THIRD_PARTY_NOTICES.md`、`SECURITY.md` を参照。

通常実行でネットワーク送信はしません。ログにはローカルパスが入る可能性があります。`--keep-debug-files` は画像／DLL／重みのコピーを残すため、公開・アップロードしないでください。
