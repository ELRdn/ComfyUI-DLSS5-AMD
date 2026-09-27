# Delivery · 0.1.0a1

> **2026-09-25 の初回納品記録です。現在の機能・実機検証・公開状態ではありません。** 最新の導入手順は [README.md](README.md) / [README.jp.md](README.jp.md)、検証範囲は [docs/TESTING.md](docs/TESTING.md)を参照してください。

**開始点:** `REPORT.html` をブラウザーで開くと、調査レポート・ロードマップ・一次資料をまとめて読めます。編集可能な正本は `REPORT_ja.md` と `ROADMAP.md` です。

**実装:** ComfyUI カスタムノード 7 種、画像／動画 CLI、外部ネイティブ接続、設定 hash、実行証拠確認、キャンセル、上書き防止、3 種の workflow（UI/API 各形式）。

**最終 CPU テスト:** 170 件、失敗 0、エラー 0、スキップ 0。Python/Comfy 型のメソッドと明示的テストダブルの契約検査、実 FFmpeg の短い動画往復を含みます。`evidence/` に証拠を保存。

**未実施:** Windows ビルド、実 RX 9070 XT の推論、実 ComfyUI サーバー・ブラウザー、GPU 性能・VRAM・画質・時間安定性。外部 DLL・EXE・重みは同梱しません。GPU 用の高画質作例も含みません。

**次の作業:** `docs/WINDOWS_SETUP.md` と `docs/HANDOFF.md` に従って、正当に利用できるローカル runtime と固定 source から、ROADMAP R2 の 1 枚実機試験を行う。

**整合性確認:** `python scripts/verify_package.py`。ローカルの配布ファイル一覧との一致を調べるもので、発行者の署名検証ではありません。ファイルを編集した後は、そのファイルの不一致が出るのが正常です。

**補足:** Python wheel のビルドもこの CPU 環境で確認しましたが、ComfyUI への導入はフォルダー配置が前提です。`scripts/render_report.py` は文書再生成用の任意ツールで、別途 mistune 3 を要します。ノードの runtime requirements には含めていません。

初回納品時点では GitHub へのリポジトリ作成・push・公開は行っていませんでした。この文書は初回納品の記録です。ZIP はソースツリーであり、第三者の非公開データやユーザーの別プロジェクト資料を含めていません。
