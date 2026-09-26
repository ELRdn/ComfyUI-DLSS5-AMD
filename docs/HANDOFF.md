# 次の開発エージェントへの引き継ぎ

## 依頼

このリポジトリを読み、**ROADMAP R2: Windows / RX 9070 XT の 1 枚実行検証**を進める。先に README、REPORT_ja.md、ROADMAP、WINDOWS_SETUP、upstream.lock、evidence/test-summary を読む。新しい別プロジェクトを増やさず、既存実装を検証する。

## 現状

0.1.0a1。Python bridge、Comfy classic ノード 7 種、CLI、RGBA8 adapter、設定 hash、実行証拠チェック、動画 FFV1/MKV、テスト、workflow は実装済み。開発元は Linux/CPU であり、Windows build・native GPU・実 Comfy browser は NOT_RUN。

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
