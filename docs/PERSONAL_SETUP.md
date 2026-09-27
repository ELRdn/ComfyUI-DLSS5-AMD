# Git clone からの個人利用セットアップ（Windows / RX 9070 XT）

この手順は各利用者が自分の PC にファイルを導入するためのものです。リポジトリ、ソース ZIP、ワークフローには NVIDIA DLL、AMD プロキシ、重み、FFmpeg を同梱しません。[AMD ランタイム v0.2.17 の利用条件](https://github.com/danielblnc/DLSS-NR-on-AMD/blob/v0.2.17/LICENSE)は**個人・非商用のみ、再配布と商用利用は禁止**です。有料製品・有料サービスとして一般客に提供するには作者の別途許諾が必要です。NVIDIA DLL の利用条件も元の入手先で確認してください。

## 利用者が用意するもの

1. Windows x64、RX 9070 XT、動作する ComfyUI とその Python。PyTorch やドライバーをこのスクリプトは入れ替えません。
2. 自分が正当に入手した **`nvngx_dlssnr.dll` 310.8.0.0**。単体 DLL か、その DLL が1個入った ZIP を指定します。通常の DLSS SR/RR/FG DLL は代用できません。DLL と ZIP の取得先をこのリポジトリは提供しません。
3. Git、CMake、Visual Studio の C++ ツール・Windows SDK・NMake が利用できる **x64 Developer PowerShell**。初回は固定ホストをソースからビルドします。
4. 1ノードの画像・動画拡大を使う場合は、`sr_amf` と AMF hwaccel が有効な Windows 用 `ffmpeg.exe`。自分で取得・インストールし、その配布元の条件を確認してください。通常の PATH の FFmpeg が AMF に対応するとは限りません。

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

## スクリプトが行うこと

- 固定した外部ホストのソースを取得・照合し、ローカルでビルドする。既存ソースがあれば検証し、変更がある場合は停止する。
- 作者の公式 v0.2.17 セットアップだけを取得し、固定サイズと SHA-256 を検証する。既存の異なるダウンロードは上書きしない。
- 指定された ZIP の中から `nvngx_dlssnr.dll` 1個だけを一時的に取り出す。DLL の x64 PE ヘッダーと FileVersion を検査する。ZIP 内の他ファイルを展開しない。
- 作者のセットアップをユーザーの PC 上で実行し、生成したプロキシと重みを固定ハッシュで照合する。新規の `config/backend.local.json` を作り、有効化する。既存設定を上書きしない。
- FFmpeg を指定した場合は、その実行ファイルの AMF 対応と SHA-256 を設定に記録する。

非公開ファイルは Git 無視対象の `local-build/` と `config/backend.local.json` に保存します。元の ZIP / DLL は変更しません。セットアップ完了は GPU 推論や画質の合格を意味しません。ComfyUI を再起動して [画像 06](../workflows/06_nr_amf_image_ONE_NODE_EXPERIMENTAL.json) または [動画 07](../workflows/07_nr_amf_video_ONE_NODE_EXPERIMENTAL.json) を読み込み、まず短い SDR 素材で確認してください。[実機検証の範囲](SCALING_VALIDATION_2026-09-27.md)と[詳しいランタイム調査](RUNTIME_SETUP_ja.md)も参照してください。
