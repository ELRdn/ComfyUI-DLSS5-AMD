# サンプル workflow

`.json` は ComfyUI UI 用、`.api.json` は API 形式。両形式で node/link と必須引数を静的検査している。実 ComfyUI サーバー／ブラウザーの統合試験は未実施。

01 は LoadImage → CPU Roundtrip → A/B Compare → SaveImage。CPU roundtrip が画像を良くすることは期待しない。画像フォーマットとノード接続の診断用。

02 は LoadImage + Settings → Native Render → 原本との A/B と単体画像保存。固定 EXE/runtime の設定が先に必要。mask は任意で、白が効果適用。初期値 mix=1 は検証のための値で、全素材に推奨する画質設定ではない。

03 は Settings → Video File。ComfyUI input の直下に短い SDR/CFR 動画を置き、選び直す。出力は可逆 MKV のパス。動画 preview/player を返す UI は未実装。

診断では解像度を変えない。拡大が必要な場合はネイティブ結果に別の超解像ノードをつなぐ。比較するときは原本側も同じ最終解像度・圧縮条件に揃える。通常の bicubic を使用する `AMDNRResize` は NOT DLSS として表示する。

画像の選択欄にある input.png と、動画の仮文字列は実ファイルへ選び直す必要がある。私物のファイルパスを workflow に埋め込んで配布しない。
