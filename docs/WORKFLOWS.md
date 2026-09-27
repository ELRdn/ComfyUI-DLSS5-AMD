# サンプル workflow

`.json` は ComfyUI UI 用、`.api.json` は API 形式。両形式で node/link と必須引数を静的検査している。2026-09-26 に実 ComfyUI API で 01 の CPU 診断、04 の設定不足時の明示的な失敗、その後のランタイム導入による 04 の実ニューラル処理と PNG 保存を確認した。

04 の UI JSON をブラウザーで開き、実行ボタンからの正常完了と出力プレビューも確認した。この再実行は直前の API 成功結果をキャッシュから再利用しており、追加の GPU 検体には数えていない。

01 は LoadImage → CPU Roundtrip → A/B Compare → SaveImage。CPU roundtrip が画像を良くすることは期待しない。画像フォーマットとノード接続の診断用。

02 は LoadImage + Settings → Native Render → 原本との A/B と単体画像保存。固定 EXE/runtime の設定が先に必要。mask は任意で、白が効果適用。初期値 mix=1 は検証のための値で、全素材に推奨する画質設定ではない。

03 は Settings → Video File。ComfyUI input の直下に短い SDR/CFR 動画を置き、選び直す。出力は可逆 MKV のパス。動画 preview/player を返す UI は未実装。

04 は RX 9070 XT 実機検証用の Native 画像ワークフロー。02 に診断ノードを追加し、結果と A/B 比較を別々に保存する。**2026-09-26 に固定ホスト・v0.2.17・検証済み fast-isolated 設定で、640×360 SDR のニューラル処理と出力を確認した。** ファイル名は `04_rx9070xt_native_validation_EXPERIMENTAL.json`。画質改善や全環境での動作保証ではない。詳細は [実機検証記録](RX9070XT_VALIDATION_2026-09-26.md) を参照。

05 は 04 の NR 結果を、別途インストールされた [ComfyUI AMD Video Upscaler](https://github.com/Yasei-no-otoko/ComfyUI-AMD-Video-Upscaler) の AMF VideoSR1.1 ノードへ送る。初期値は 2 倍、`backend=amf_sr`、`fallback_policy=error`。ポータブル JSON の `ffmpeg_path` は `ffmpeg` なので、AMF 対応 FFmpeg を選び直す。この PC では通常の PATH が AMF 非対応版を指すため、個人用に保存した `AMDNR_RX9070XT_AMF_SR_2倍.json` には対応版の絶対パスを設定済み。**NR 自体の出力サイズは不変**で、拡大は AMF の別工程。640×360 起点では 8 倍、1920×1080 起点では 4 倍まで短時間の実行確認をした。画質上の上限は [倍率検証記録](SCALING_VALIDATION_2026-09-27.md) を参照。

**現在の1ノード版は 06/07。** `06_nr_amf_image_ONE_NODE_EXPERIMENTAL.json` は LoadImage → `AMDNRRenderUpscale` → SaveImage。factor と mix を同じノードで設定し、NR と後段の AMD AMF VideoSR1.1 を一度に実行する。`07_nr_amf_video_ONE_NODE_EXPERIMENTAL.json` は `AMDNRVideoUpscaleFile` の1ノードで、ComfyUI input 直下の短い SDR/CFR 動画を処理して音声コピー付き FFV1/MKV を保存する。両者は外部の ComfyUI AMD Video Upscaler ノードを必要としない。AMF 対応 FFmpeg は [導入手順](WINDOWS_SETUP.md)に従ってサーバー側の `backend.local.json` にハッシュで固定する。05 は以前の2ノード構成を再現する比較用として残す。

06/07 は RX 9070 XT の実 ComfyUI API で、640×360→1280×720 の画像 PNG と、3フレーム・音声付き動画 640×360→1280×720 の MKV 出力に成功。動画は3フレームとも NR と VideoSR1.1 が完了し、FPS、音声ペイロード、フレーム数、出力サイズを検査した。詳細は [倍率検証記録](SCALING_VALIDATION_2026-09-27.md)。UI JSON は構造検査済みで、ブラウザーからの手動実行は今回まだ行っていない。

01～04 の診断・NR 専用 workflow では解像度を変えない。拡大する場合は 06/07 の統合ノードを選ぶ。05 は外部 AMF ノードをつなぐ比較用。比較するときは原本側も同じ最終解像度・圧縮条件に揃える。通常の bicubic を使用する `AMDNRResize` は NOT DLSS として表示する。

画像の選択欄にある input.png と、動画の仮文字列は実ファイルへ選び直す必要がある。私物のファイルパスを workflow に埋め込んで配布しない。
