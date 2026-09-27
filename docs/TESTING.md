# テストと証拠の読み方

## 再実行

リポジトリ直下の、NumPy/Pillow/PyTorch/pytest/coverage が使える Python 環境で実行する。

```powershell
python -m pytest -q
python scripts/collect_evidence.py
```

FFmpeg と FFprobe がなければ実動画のテストは skip になる。したがって exit 0 だけでなく **skipped の件数と理由**も読む。`evidence/environment.json` と `evidence/test-summary.json` は **2026-09-25 の Linux/CPU 初回納品スナップショット**で、現在の 9 ノードや Windows 実機確認を含まない。初回の全テスト JUnit は `evidence/junit.xml`。実機の結果は下記の検証記録を、現在のコードの結果は上記コマンドの再実行結果を参照する。

## 検証層

| 層 | 実行したこと | 証明しないこと |
|---|---|---|
| CPU 数値 | 形状・値域・RGBA8・alpha・mix/mask | ニューラル画質 |
| ファイル／設定 | JSON・hash・exclusive publish・lock | バイナリの発行者の正当性 |
| Native 契約 | 偽 EXE 役の Python subprocess を介した正常／異常報告 | DLL ロード・実 GPU 推論 |
| Comfy メソッド | package import・INPUT_TYPES・tensor 入出力 | 実 Comfy サーバー／フロントエンドの互換性 |
| FFmpeg 実処理 | 6 フレームの可逆画素・順序・音声 hash の一致 | 長時間、全 codec、完全な AV timestamp 保持 |
| Windows 実機 | RX 9070 XT / v0.2.17 の 640×360～1920×1080 SDR 入力で NR 完了。AMF VideoSR1.1 は 640×360 起点で最大 8 倍、1920×1080 起点で最大 4 倍の短い合成画像試験に成功。統合ノードで画像 2 倍・8 倍、音声付き 3 フレーム動画 2 倍を ComfyUI API から保存。[NR 実機記録](RX9070XT_VALIDATION_2026-09-26.md)・[拡大実機記録](SCALING_VALIDATION_2026-09-27.md) | 自然画像の品質、長い動画、音声 timestamp 同期、長時間安定性、UI からの 06/07 手動実行 |

`tests/support/fake_engine.py` は、先頭からテスト専用と記載したエンジン役である。ハッシュ・報告・process の挙動だけを試す。画像の赤チャネルを人工的に変える場合があるが、ニューラル推論ではない。作例として使わない。

## カバレッジ

`coverage-summary.txt` の数字は Python の実行行／分岐の観測であり、製品品質の百分率ではない。Windows 固有処理やエラー分岐の一部には未実行箇所がある。GPU エンジンは計測対象コードに含めていない。

## 追加する実機テスト

ROADMAP R2/R3 に従い、1 枚、A/B/A、複数解像度、6/24/120 フレーム、cancel、timeout、GPU index、正常復帰を記録する。ハードウェアテストは opt-in とし、通常の CPU テストに混ぜて勝手に DLL を実行しない。

設定、ファイル SHA、入力 SHA、出力 SHA、実行ログ、Windows/driver/Comfy/Python/torch の版、cold/warm の区別を記録する。私物素材・モデル・DLL は evidence フォルダーへ公開しない。

## リグレッション方針

完了検査を緩めてテストを通す修正は禁止。タイムアウトを無制限にする修正、失敗時に元画像を返す修正、fake engine の結果を実推論として記録する修正は禁止する。高速化は exact input/output と品質セットを比較してから昇格する。
