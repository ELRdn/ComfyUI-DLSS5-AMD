# Windows / RX 9070 XT 導入と最初の検証

Git clone 後に個人利用のセットアップを一括で進める場合は、[配布元リンクと ZIP 対応手順](PERSONAL_SETUP.md)を先に参照してください。この文書は各工程を手動で確認するための詳細手順です。ROCm の導入だけでは作者の NR ランタイムや AMF 対応 FFmpeg は入りません。

**確認範囲:** 2026-09-26 に Windows ビルド、RX 9070 XT の 640×360 SDR ニューラル処理、ComfyUI API での PNG 保存を確認しました。通常の待機設定での失敗と、ローカル検証後に有効化した fast-isolated 設定は [実機記録](RX9070XT_VALIDATION_2026-09-26.md) に記載しています。ドライバー、Python、PyTorch を自動更新する手順ではありません。

## 1. フォルダーと Python を確認

リポジトリを以下のように配置します。ZIP を二重フォルダーにして `__init__.py` がさらに奥に入らないようにしてください。

```text
ComfyUI/
  custom_nodes/
    ComfyUI-DLSS5-AMD/
      __init__.py
      amd_nr/
      scripts/
      config/
      README.md
```

通常インストールと Portable では Python の場所が違います。ComfyUI の起動スクリプト／ログを見て、**ComfyUI が実際に使う Python の絶対パス**を指定します。以下の C: や D: は配置例であり、ひろなおの環境を自動検出したものではありません。

```powershell
$Repo = 'C:\ComfyUI\custom_nodes\ComfyUI-DLSS5-AMD'
$Py = 'C:\ComfyUI\venv\Scripts\python.exe'  # 自分の実際の Python に変更
Set-Location $Repo
& $Py -c "import sys, torch; print(sys.executable); print(torch.__version__); print(torch.version.hip)"
& $Py -m amd_nr doctor
```

Portable なら `$Py` が `...\python_embeded\python.exe` である場合があります。ここで別の Python を選ぶと、ノードの依存を別環境へ入れてしまいます。

NumPy/Pillow が既にあれば、そのまま先へ進めます。足りない場合だけ、バックアップした適切な環境で次を実行します。Torch の再インストールは行いません。

```powershell
& $Py -m pip install -r requirements.txt
& $Py -m amd_nr selftest --output selftest-output
```

この selftest は CPU の転送診断だけです。成功しても DLSS が動いたことにはなりません。

## 2. 固定したホストのソースを取得

Git が必要です。次のスクリプトは、ユーザーが実行した時だけ GitHub へアクセスします。固定されたソースのみを取得し、外部 DLL／モデル／ドライバーは取得しません。

```powershell
& $Py scripts/fetch_upstream.py
& $Py scripts/fetch_upstream.py --verify-only
```

既定の取得先は `third_party/DLSS5-AMD-Video`。既存ディレクトリを消去・reset する動作はありません。取得が失敗して一部だけ残った場合も、そのフォルダーを勝手に再利用しません。中身を確認したうえで別の新規 destination を指定するか、自分で不要な取得物を整理してください。

公開コード、LICENSE、native README を読み、実行内容を確認します。ハッシュ一致は公開者の信頼性や安全性の保証ではありません。

## 3. ホストをビルド

Visual Studio の **x64 Developer PowerShell** を開きます。C++ ツール、Windows SDK、CMake、NMake が必要です。ここではそれらを自動インストールしません。`cl`、`nmake`、`cmake` が見つからない場合は、開発環境を確認してください。

```powershell
$Repo = 'C:\ComfyUI\custom_nodes\ComfyUI-DLSS5-AMD'
$Py = 'C:\ComfyUI\venv\Scripts\python.exe'
Set-Location $Repo
.\scripts\build_native.ps1 -Python $Py
```

既定では `local-build/native/dlss5_video_native.exe` と `build-record.json` ができます。再ビルド時は新しい `-BuildDirectory` を使ってください。既存ビルドの上書きや削除はしません。

PowerShell がスクリプト実行を拒否する環境では、セキュリティ設定を下げず、組織／PC の方針に従って確認済みのコマンドを Developer PowerShell で個別実行する方法を選びます。本リポジトリは実行ポリシー変更を要求しません。

この EXE はホストであり、モデルそのものではありません。ビルド成功だけでは GPU 推論はまだできません。

## 4. 正当に利用できるローカルランタイムを設定

`nvngx_dlssnr.dll` 310.8.0.0 を用意できる場合は、[ランタイム導入ガイド](RUNTIME_SETUP_ja.md) の `scripts/setup_runtime.py` を利用できます。固定 v0.2.17 の公式セットアップ取得、ローカル生成、ハッシュ照合、設定作成をまとめて実行します。以下は既に 3 ファイルを持っている場合の手動設定です。

選択したホストが要求する、対応版のローカルファイルを別の非公開フォルダーに用意します。

```text
C:\AMDNR-private-runtime\
  version.dll  または version.dll.bak
  nvngx_dlssnr.dll
  dlssnr_on_amd_weights.bin
```

ホスト、AMD ランタイム、NVIDIA DLL、重みの組合せを作者の資料と照合してください。異なる AMD プロジェクトの DLL を名前だけ合わせて混在させないでください。本リポジトリにはこれらの取得・抽出・再配布の権限は含まれず、自動取得も行いません。

正当に使用できるファイルをまだ用意できない場合は、ここで止めます。CPU reference を DLSS の代わりとして扱わないでください。

```powershell
& $Py -m amd_nr init-config `
  --engine "$Repo\local-build\native\dlss5_video_native.exe" `
  --runtime-dir 'C:\AMDNR-private-runtime' `
  --work-root 'D:\AMDNR-work' `
  --output "$Repo\config\backend.local.json"
```

生成される設定は `trusted_local_artifacts=false` です。内容、出所、利用権限、ハッシュ、作業フォルダーの空き容量を確認したうえで、人間が true に変更します。SHA-256 は改変検知であり、出所の正当性を自動保証しません。

`hip_device` は初期値 null。PC によって iGPU と dGPU の番号が違います。外部ランタイムの GPU 一覧やログを使って 9070 XT に対応する数値を確認し、必要なら文字列 `"0"` や `"1"` などを設定します。作者の環境が 1 だったという理由だけで 1 を設定しないでください。

`HIP_VISIBLE_DEVICES` は本ブリッジが子プロセスにだけ設定します。システム全体の環境変数を変更する必要はありません。

`fast_isolated` は false のまま開始します。組合せを検証する前に高速化フラグを有効化しないでください。

## 5. 最初の 1 枚

自分が利用権限を持つ、特徴のある SDR/sRGB 画像を用意します。最初は 640×360 などの偶数サイズを推奨します。これはテスト入力の選択であって、勝手に画像を縮小する機能ではありません。

CLI は ICC つき画像、CMYK、高ビット深度を拒否します。画像編集アプリ等で明示的に SDR/sRGB へ変換し、必要なタグ処理を行ってください。

```powershell
& $Py -m amd_nr doctor
& $Py -m amd_nr image `
  'C:\AMDNR-test\input-sdr.png' `
  'C:\AMDNR-test\output-native-001.png' `
  --backend native
```

既存 output は上書きしません。毎回別名にしてください。

表示された `manifest.json` の場所を確認します。status、input/output の寸法、evidence、runtime hash、処理秒数を確認し、ログに意図した GPU が出ているかを確かめます。完成画像の色・向き・黒崩れ・細部も確認します。

`doctor` の `native_gpu_smoke_test=NOT_RUN` は、この診断呼び出し自身が GPU を起動しないことを示します。過去の全ジョブを検索して判定する機能ではありません。

## 6. ComfyUI で試す

ComfyUI を再起動し、起動ログに読み込みエラーがないことを確認します。`workflows/01_cpu_transport_NOT_DLSS.json` を読み込み、Load Image を選び直して診断します。

次に `02_native_image_EXPERIMENTAL.json` を読み込みます。R2 と同じ入力で処理し、CLI と同じ条件になるか比較します。effect_mask は任意入力です。LoadImage の反転 alpha をそのまま接続するのではなく、「白で適用する」範囲を確認してください。

従来の 05 ワークフローは、ネイティブ処理後に外部の AMF ノードを接続する例です。`AMDNRResize` は bicubic の通常拡大で、学習済み超解像や FSR4 ではありません。

### 1ノードの NR + AMF VideoSR1.1

画像・動画の拡大には、`sr_amf` と AMF ハードウェアアクセラレーションを備えたローカル FFmpeg を用意します。既存の NR 用 `backend.local.json` に、その実行ファイルの実体パスと SHA-256 を固定します。`ffmpeg` コマンドが PATH にあるだけでは不十分です。この PC では通常の PATH が AMF 非対応版を選ぶため、対応版を明示しました。

```powershell
& $Py scripts/setup_runtime.py configure-amf `
  --ffmpeg 'C:\path\to\AMF-enabled\ffmpeg.exe' `
  --config "$Repo\config\backend.local.json"
```

ComfyUI に別コピーをインストールした場合は、`--config` に**そのコピーの** `config/backend.local.json` を指定します。設定済みの異なる FFmpeg を更新する際は内容を確認し、`--replace` を付けます。ツールは実行ファイル、`sr_amf` フィルター、AMF hwaccel を検査します。ダウンロード、ドライバー変更、CPU 拡大への切替は行いません。

RX 9070 XT が PCI デバイス ID `7550` のこの PC では、上記コマンドへ `--device-id 7550` を追加して、毎回の AMF ログが同じ GPU を選んだか検査しています。別の PC ではデバイス ID を確認してから指定するか、省略します。指定した ID と異なる GPU が選ばれた場合、出力を採用しません。

ComfyUI 再起動後、画像は `workflows/06_nr_amf_image_ONE_NODE_EXPERIMENTAL.json`、動画は `workflows/07_nr_amf_video_ONE_NODE_EXPERIMENTAL.json` を読み込みます。06 は画像を選び、factor=2 から始めます。07 は短い SDR/CFR 動画を ComfyUI input 直下へ置いて選び、まず `max_frames` を実際のフレーム数に合わせます。どちらも mix を同じノードで設定できます。05 のような外部アップスケーラーノードは不要です。

NR の入力上限は既定で 1920×1080、後段の拡大出力は各辺 8192 以下、factor は整数 2～8 です。動画は音声をコピーし、可逆 FFV1/MKV を生成します。容量が大きくなるため、空きディスクの検査を行います。動画も深度・動きベクトル・履歴を NR に供給しないため、ゲームのリアルタイム経路とは異なります。[実機の画像・動画結果](SCALING_VALIDATION_2026-09-27.md)を参照してください。

## 7. 動画へ進む

最初は 6 フレーム程度、問題なければ 24、120 と増やします。SDR、CFR、単一映像ストリーム、回転情報なし、square pixel、開始時刻がゼロ付近の書き出しを使います。

```powershell
& $Py -m amd_nr video `
  'C:\AMDNR-test\clip-sdr-cfr.mkv' `
  'C:\AMDNR-test\clip-native-001.mkv' `
  --backend native --chunk-frames 1 --max-frames 120
```

`max-frames` を超えた動画は拒否します。自動で途中を切り取る設定ではありません。トリムは編集ソフトなどで明示的に行います。

出力は可逆 FFV1/RGB8 の MKV。再生 FPS と処理速度は別です。音声ペイロードを hash 照合しますが、音声の全 timestamp を独立検証する機能は未実装なので、実際の再生による同期確認も行います。

ComfyUI では、短い入力動画を ComfyUI の `input` 直下へ置き、`03_native_video_EXPERIMENTAL.json` の動画欄で選び直します。結果は `output/amd_nr/` に生成され、ノードはファイルパスと実行記録を返します。独自の動画プレーヤー UI は未実装です。

## 8. トラブルシュート

| 症状 | 確認すること |
|---|---|
| `Native backend is not configured` | ComfyUI のプロセスが読む `config/backend.local.json` または `AMD_NR_CONFIG` |
| `SHA-256 mismatch` | ファイル更新・誤ったパス。出所を確認せず hash を再生成して通さない |
| `invalid kernel file` など | runtime と GPU architecture、iGPU/dGPU の選択。GPU index の決め打ちを避ける |
| 完了 JSON がない／カウント不一致 | native log、runtime/host の版、正しい `--out`。完了条件を緩めない |
| 入力サイズで拒否 | 初期値は幅1920×高さ1080以内、偶数。縦長も高さ制約を受ける |
| 容量不足 | raw とランタイム一時コピーに必要な空き容量。作業先を十分なローカルボリュームへ |
| Atomic publication failed | 出力先が hardlink 対応のローカル NTFS 等か。クラウド同期領域や一部外部メディアは避ける |
| 画像がほぼ変わらない／不自然 | 実行証拠と品質を別に確認。mix や素材適性を評価し、無理に採用しない |

## 9. 戻し方

ComfyUI を終了し、カスタムノードのフォルダーを `custom_nodes` の外へ移動します。本コードはドライバーやシステム DLL を変更しません。作業フォルダーはジョブ終了を確認してから、自分で不要なジョブだけを削除します。

`keep-debug-files` を使った場合、フォルダーには画像・DLL・重みが残ります。トラブル報告へ丸ごと添付しないでください。ログも個人パスを確認してから共有します。
