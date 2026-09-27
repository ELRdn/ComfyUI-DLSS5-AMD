# 次の開発エージェントへの引き継ぎ

## 依頼

[NR 実機検証記録](RX9070XT_VALIDATION_2026-09-26.md)と[拡大検証記録](SCALING_VALIDATION_2026-09-27.md)から続ける。画像と3フレーム動画の短い経路は実行済み。次に何を検証するかは依頼範囲に合わせ、ROADMAP R2/R3 の未実施ゲートを一括で合格扱いしない。

## 現状

0.1.0a1。Python bridge、Comfy classic ノード 9 種、CLI、RGBA8 adapter、設定 hash、実行証拠チェック、動画 FFV1/MKV、テスト、workflow は実装済み。2026-09-26 に RX 9070 XT で異なる 640×360 SDR 合成画像 2 枚、CLI、実 ComfyUI API のニューラル処理と PNG 保存を確認した。2026-09-27 には NR を入力サイズで実行し、後段の AMD AMF VideoSR1.1 で拡大する統合画像・動画ノードも API から実行した。画像は 2 倍・8 倍、音声付き 3 フレーム動画は 2 倍を確認した。[拡大検証記録](SCALING_VALIDATION_2026-09-27.md)を参照。自然写真の品質、長い動画、音声 timestamp 同期、持続運用は未検証。

ランタイム導入補助は `scripts/setup_runtime.py`、固定値は `runtime.lock.json`、調査は [RUNTIME_SETUP_ja.md](RUNTIME_SETUP_ja.md)。利用者が `dlssnr_setup/` で手動生成した v0.2.17 の proxy / weights は固定値に一致した。DLL 不足は解消済み。HIP 6/7 では RX 9070 XT が index 1、内蔵 GPU が index 0。子の `HIP_VISIBLE_DEVICES=1` で絞ると RX 9070 XT が device 0 になり、実ログでも確認した。

通常の待機設定では画像回収条件を満たさず失敗。既存 `--fast-isolated` の 2 枚検証を通してからローカル設定を有効化した。作業用と実 ComfyUI 側の `backend.local.json` は同じ検証済みファイルを参照する。完了条件、ホストソース、配布設定の既定値は変更していない。補助ツールの自動 `install` 正常系は未実行。

外部ホストの基準は eikkapine/DLSS5-AMD-Video `9303dfaa14c2ca83e237ff18318bdfc0b767f6fb`。上流 source はこの ZIP に vendoring していない。`fetch_upstream.py` が明示実行時にのみ取得する。DLL・EXE・weights・ONNX は含まない。

## 守る制約

既存 ROCm/PyTorch を勝手に置き換えない。GPU/driver を推測しない。利用者に正当な権限がある runtime だけを使う。セキュリティ設定や管理者権限を要求しない。ゲームへの注入や画面キャプチャに拡張しない。

CPU reference や fake engine を DLSS 実行と記録しない。native の失敗を原画像コピーへ差し替えない。JSON の完了条件を緩めて通さない。fast-isolated は exact hash の組合せを検証してから opt-in。

## 実行順

環境の read-only 診断 → 既存テスト → 固定 source 取得・レビュー → native build → disabled config 生成 → 利用者による出所・利用権限確認 → 1 枚の native 実行 → R2 のチェック。

必要なローカルファイルが足りなければ、missing の具体名を報告し、そのゲートを未完了にする。互換性を推測して他プロジェクトの DLL を混ぜない。ネットワークや権限の問題を隠さない。

## 成果報告

変更ファイル、テストコマンドと結果、実行した GPU/driver、host/runtime SHA、出力形状と hash、壁時計秒、目視した問題、未実施項目、次の 1 ステップを報告する。commit/push/deploy は利用者の依頼範囲に従う。

実 ComfyUI と Windows スクリプトが動いたときだけ、そのゲートを更新する。README の未検証表示をまとめて消さず、検証した範囲を限定して置き換える。
