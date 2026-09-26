# Windows / RX 9070 XT 導入と最初の検証

**重要:** この手順は、公開されたホスト仕様に基づいて作成・コードレビューしたものです。今回の開発環境では Windows ビルドと GPU 推論を実行していません。ドライバー、Python、PyTorch を自動更新する手順ではありません。

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

ネイティブ処理後に通常の超解像を使う場合は、別ノードとして接続します。`AMDNRResize` は bicubic の通常拡大で、学習済み超解像や FSR4 ではありません。

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
