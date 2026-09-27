# Architecture / 契約

## 分離単位

- `nodes.py`: ComfyUI の入出力・サーバー設定のロード。プロセス引数を workflow から受け取らない。
- `contracts.py`: BHWC、RGB/RGBA、値域、マスク、合成、保守的メモリ上限。
- `config.py`: 固定ファイルパス、SHA-256、明示的な有効化、runtime hash ごとの fast opt-in。
- `backends.py`: reference と native の分離。上流 RGBA8/CLI/INI への具体的アダプター。
- `evidence.py`: 完了レポートと出力の検証。実行報告と品質証明を混同しない。
- `pipeline.py`: 排他、個別ジョブ、ハッシュ、実行、合成、記録、後始末。
- `process.py`: shell-free、子プロセス環境、タイムアウト、キャンセル、ログ制限。
- `filesystem.py`: JSON 検査、空き容量、OS lock、非上書きの最終公開。
- `video.py`: FFmpeg/FFprobe、CFR 格子、chunk 処理、FFV1 出力、音声ペイロード比較。
- `amf.py`: ネイティブ NR 後の別工程として、設定に固定した FFmpeg の `sr_amf` / VideoSR1.1 を実行。DLSS の超解像ではない。
- `runtime_setup.py`: 作者の固定ランタイム取得と、利用者が用意した NR DLL の検査・ローカル生成物の照合。外部バイナリは配布しない。
- `cli.py`: 手元のファイルで再現するための入口。GPU 依存を勝手に導入しない。

## 画像契約

入力 BHWC float [0,1]。ComfyUI の標準は C=3、CLI/一部呼び出しでは C=4 も受理。HDR ではないことを利用者が保証する。出力は CPU float32 BHWC。同じ batch・寸法・順序。RGBA8 へ量子化した RGB のみが native へ渡り、original alpha を維持する。

上記の寸法維持は NR 段階の契約。統合画像ノード `AMDNRRenderUpscale` は RGB 入力だけを受け取り、NR 完了後に別工程の AMF VideoSR1.1 で出力寸法を拡大する。

`output = original + mix × mask × (native - original)` を RGB に適用する。mask なしは 1。白で効果、黒で原本保持。mix=0 でも native 選択時は native の実行を行う。省略した推論を「完了」と偽らないためである。

画像全体の tiling、モデルの torch.compile、FP8 変換、FSR、optical flow、temporal history は本アダプターにない。

## native job

毎回新しい非公開 job ディレクトリに、検査済み EXE、runtime、INI、input.rgba を配置する。上流仕様の `--proxy --out` は private D3D12 ホスト用であり、本ブリッジがゲームに注入する機能ではない。

終了コード、JSON の completed/enabled/status/error、input/output/neural 完了 frame 数、二つ以上の logged jobs per frame、raw byte 数を確認する。どれかが不成立なら例外と failed manifest を返す。

証拠の粒度は `native_coordinator_report`。子ワーカーの fence と log 検査は上流ホストに委ねる。改ざんされたホストが嘘の JSON を出すケースをブリッジだけで防げるとは主張しない。利用者の信頼境界・hash・ソースレビューが必要。

## リソースと残る限界

RAM 予算は `B×H×W×128 bytes` の保守的概算。これは当該コードでの事前チェックであり、Python allocator、ComfyUI に常駐するモデル、ドライバーの VRAM、システム全体の空きを保証しない。

同じ設定 work_root の native job は OS lock で直列化する。別 work_root、別プロセス、他アプリの GPU 使用まで管理しない。

Windows 停止は taskkill と上流 native coordinator の Job Object に依存する。実 Windows での停止検証は残る。POSIX では process group を停止し、異常終了した親から残った子も終了するテストを実行した。

動画は CPU RAM を chunk 単位にする一方、raw 入出力は全長を保持する。ログと job manifest は残し、通常は画像／DLL／重みの一時コピーを削除する。保持したデバッグデータは自動公開しない。

## 後続バックエンド

lmxxf の C ABI は Python 型の ndarray API ではない。D3D12 resource state と GPU queue の順序、session/frame ID、retire/drain、device lost を実装する専用 host が必要。新プロトコルは schema を分け、既存の baseline を残して同条件比較する。
