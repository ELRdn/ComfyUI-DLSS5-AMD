# Git clone からの個人利用セットアップ（Windows / RX 9070 XT）

この手順は各利用者が自分の PC にファイルを導入するためのものです。リポジトリ、ソース ZIP、ワークフローには NVIDIA DLL、AMD プロキシ、重み、FFmpeg を同梱しません。[AMD ランタイム v0.2.17 の利用条件](https://github.com/danielblnc/DLSS-NR-on-AMD/blob/v0.2.17/LICENSE)は**個人・非商用のみ、再配布と商用利用は禁止**です。有料製品・有料サービスとして一般客に提供するには作者の別途許諾が必要です。NVIDIA DLL の利用条件も元の入手先で確認してください。

## 利用者が用意するもの

1. Windows x64、RX 9070 XT、動作する ComfyUI とその Python。PyTorch やドライバーをこのスクリプトは入れ替えません。
2. 自分が正当に入手した **`nvngx_dlssnr.dll` 310.8.0.0**。単体 DLL か、その DLL が1個入った ZIP を指定します。通常の DLSS SR/RR/FG DLL は代用できません。DLL と ZIP の取得先をこのリポジトリは提供しません。
3. Git、CMake、Visual Studio の C++ ツール・Windows SDK・NMake が利用できる **x64 Developer PowerShell**。初回は固定ホストをソースからビルドします。
4. 1ノードの画像・動画拡大を使う場合は、`sr_amf` と AMF hwaccel が有効な Windows 用 `ffmpeg.exe`。自分で取得・インストールし、その配布元の条件を確認してください。通常の PATH の FFmpeg が AMF に対応するとは限りません。

## 配布元と、混同しやすい依存関係

| 部品 | 配布元・確認先 | このリポジトリでの扱い |
|---|---|---|
| AMD 向け NR ランタイム | [作者のソース](https://github.com/danielblnc/DLSS-NR-on-AMD)・[固定 v0.2.17 リリース](https://github.com/danielblnc/DLSS-NR-on-AMD/releases/tag/v0.2.17)・[LICENSE](https://github.com/danielblnc/DLSS-NR-on-AMD/blob/v0.2.17/LICENSE) | 本人の PC 上で作者のリリースから取得・ハッシュ検証。ROCm に同梱される部品ではありません |
| NR ホストのソース | [eikkapine/DLSS5-AMD-Video の固定リビジョン](https://github.com/eikkapine/DLSS5-AMD-Video/tree/9303dfaa14c2ca83e237ff18318bdfc0b767f6fb) | clone 後に固定リビジョンを取得・検証してローカルビルド |
| NVIDIA NR DLL | [NVIDIA 公開 DLSS SDK の確認済みツリー](https://github.com/NVIDIA/DLSS/tree/374959484e79a640feaba44c93ac8cfb0a03f5b5/lib/Windows_x86_64)には対象の `nvngx_dlssnr.dll` がありません | 確認済みの公式公開ダウンロード URL はありません。本人が利用権限のあるローカルファイルを指定します。第三者の DLL ミラーは案内しません |
| AMF 対応 FFmpeg | [FFmpeg 公式のダウンロード案内](https://ffmpeg.org/download.html)・[Gyan の Windows ビルド](https://www.gyan.dev/ffmpeg/builds/) | 利用者が別途入手した `ffmpeg.exe` を検査し、ローカル設定に SHA-256 で固定。すべてのビルドが `sr_amf` に対応するとは限りません |
| AMF 拡大の参考ノード | [ComfyUI AMD Video Upscaler](https://github.com/Yasei-no-otoko/ComfyUI-AMD-Video-Upscaler) | 旧 05 workflow の比較用。現在の 06/07 はこの外部ノードを追加せず、同じカスタムノード内で FFmpeg の `sr_amf` を呼びます |

**非公式 ZIP について:** 利用者が挙げた [RenoDX DLSS Installer の issue #1](https://github.com/yumlevi/renodx-dlss-installer/issues/1) は、同プロジェクトの `streamline.zip` に含まれた DLL の SHA-256 を報告しています。この PC の提供 DLL はその値 `ceb6432f6fbdf44d886014bcd47241932bf8b67439feef9bbdd0961436662650` と一致しました。ただし、このローカル DLL の Windows Authenticode 状態は `HashMismatch` です。同リポジトリ自身も Streamline/DLSS DLL を NVIDIA の proprietary ファイルと説明しています。これは入手経路を裏付ける情報であり、NVIDIA 公式配布や第三者による再配布権の確認にはなりません。`latest` は更新可能な release なので、現在の ZIP の中身もこの記録だけでは固定できません。本セットアップはこの非公式 ZIP を自動取得しません。

**ROCm、AMD 向け NR ランタイム、AMF VideoSR1.1 は別物です。** ROCm/PyTorch が動く ComfyUI でも、NR 用のプロキシ・重み・NVIDIA DLL は自動的にはそろいません。AMF 側も Windows の対応 GPU/ドライバーと `sr_amf` 対応 FFmpeg が必要です。AMF は NR の後段で拡大するためのもので、NR の代わりにはなりません。

「自己責任」は利用条件や再配布禁止を免除する意味ではありません。各配布元の条件、手元のファイルの出所、対応版を確認してから導入してください。このリポジトリの MIT ライセンスが適用されるのは本リポジトリの自作コードです。

## 導入

ComfyUI の実際の `custom_nodes` フォルダーに clone します。以下のパスは例なので各自の配置に置き換えてください。

```powershell
Set-Location 'C:\path\to\ComfyUI\custom_nodes'
git clone https://github.com/ELRdn/ComfyUI-DLSS5-AMD.git
Set-Location .\ComfyUI-DLSS5-AMD
$Py = 'C:\path\to\ComfyUI\.venv\Scripts\python.exe'
$OwnedZip = 'C:\path\to\your-owned-files.zip'
$AmfFfmpeg = 'C:\path\to\AMF-enabled\ffmpeg.exe'
& .\scripts\setup_personal.ps1 -Python $Py -ModelZip $OwnedZip -FFmpeg $AmfFfmpeg -AcceptRuntimeLicense
```

DLL 単体なら `-ModelDll 'C:\path\to\nvngx_dlssnr.dll'` を `-ModelZip` の代わりに使います。PowerShell がスクリプトを拒否する場合、このツールは実行ポリシーやセキュリティ設定の変更を求めません。PC の方針に従って、確認済みのスクリプトを実行してください。

セットアップは、複数の HIP ライブラリーを調べて RX 9070 XT の index が一意に一致した場合だけ自動選択します。一致しない場合は停止するので、`python scripts/setup_runtime.py probe-hip --library amdhip64_6.dll` 等で実機を確認し、`-HipDevice 1` のように指定してください。ComfyUI/PyTorch の `cuda:0` と HIP index は同じとは限りません。

`-FFmpeg` を省略すると NR の設定までは完了しますが、06/07 の1ノード拡大は使用できません。後から `python scripts/setup_runtime.py configure-amf --ffmpeg 'C:\path\to\ffmpeg.exe' --config config\backend.local.json` で追加できます。FFmpeg は `sr_amf` / AMF を確認して SHA-256 で固定します。GPU の選択をさらに固定する場合は `--device-id` を指定してください。

手動で FFmpeg を確認する場合は、選んだ実行ファイルに対して次を実行します。両方に該当項目があり、`configure-amf` も通ることを確認してください。

```powershell
& $AmfFfmpeg -hide_banner -filters | Select-String 'sr_amf'
& $AmfFfmpeg -hide_banner -hwaccels | Select-String 'amf'
```

## スクリプトが行うこと

- 固定した外部ホストのソースを取得・照合し、ローカルでビルドする。既存ソースがあれば検証し、変更がある場合は停止する。
- 作者の公式 v0.2.17 セットアップだけを取得し、固定サイズと SHA-256 を検証する。既存の異なるダウンロードは上書きしない。
- 指定された ZIP の中から `nvngx_dlssnr.dll` 1個だけを一時的に取り出す。DLL の x64 PE ヘッダーと FileVersion を検査する。ZIP 内の他ファイルを展開しない。
- 作者のセットアップをユーザーの PC 上で実行し、生成したプロキシと重みを固定ハッシュで照合する。新規の `config/backend.local.json` を作り、有効化する。既存設定を上書きしない。
- FFmpeg を指定した場合は、その実行ファイルの AMF 対応と SHA-256 を設定に記録する。

非公開ファイルは Git 無視対象の `local-build/` と `config/backend.local.json` に保存します。元の ZIP / DLL は変更しません。**新規 PC での一括セットアップ完走は未検証**であり、セットアップ完了だけでは GPU 推論や画質の合格になりません。ComfyUI を再起動して [画像 06](../workflows/06_nr_amf_image_ONE_NODE_EXPERIMENTAL.json) または [動画 07](../workflows/07_nr_amf_video_ONE_NODE_EXPERIMENTAL.json) を読み込み、まず短い SDR 素材で確認してください。ノード読み込み時に NumPy/Pillow が不足する場合だけ、ComfyUI が使う Python で `-m pip install -r requirements.txt` を実行します。PyTorch はこの requirements に含みません。[実機検証の範囲](SCALING_VALIDATION_2026-09-27.md)と[詳しいランタイム調査](RUNTIME_SETUP_ja.md)も参照してください。
