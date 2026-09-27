# RX 9070 XT 用ランタイムの導入調査と手順

調査日: **2026-09-26**。対象は、このブリッジが接続する非公式 AMD Neural Rendering の静止画／動画ファイル処理です。

## 結論と、利用者に必要なもの

利用者が用意する元ファイルは **`nvngx_dlssnr.dll`、Windows x64、FileVersion `310.8.0.0`** です。正当に入手した対応ゲーム等のローカルコピーを指定します。通常の `nvngx_dlss.dll`、`nvngx_dlssd.dll`、`nvngx_dlssg.dll` では代用できません。

この DLL があれば、AMD 向けランタイム作者のセットアップがプロキシ DLL と重みを生成します。このリポジトリに追加した補助ツールで、セットアップの取得、SHA-256 照合、元 DLL の版確認、生成物の検証、ComfyUI が読む設定の作成まで実行できます。

**2026-09-26 追記:** 利用者が `dlssnr_setup/` で v0.2.17 セットアップを実行し、生成物の検証が完了しました。RX 9070 XT で 640×360 SDR の実ニューラル処理と ComfyUI PNG 保存も成功しています。手動インストールの生成物を再利用したため、補助ツールの `install` 正常系の自動実行は未検証です。[実機記録](RX9070XT_VALIDATION_2026-09-26.md)に条件と失敗例を記載しています。

新しく導入する利用者に必要なのは、以下のファイルと利用条件の確認です。この PC では必要ファイルがそろっています。

1. 利用権限のある **`nvngx_dlssnr.dll` 310.8.0.0 の保存先**。このファイルは自動ダウンロードしません。調査した NVIDIA 公開 SDK のツリーには NR DLL がありませんでした。
2. **AMD ランタイムの利用条件に適合するか**。v0.2.17 の LICENSE は個人・非商用利用を許可し、商用利用と再配布を禁止しています。商用の画像制作・サービス等で使う場合は作者から別の許諾が必要です。ブリッジの MIT ライセンスだけでは外部ランタイムの商用利用は許可されません。NVIDIA DLL の利用条件も元の配布物に従います。

初回調査では Steam/Epic ライブラリの 2 か所に DLL は見つかりませんでした。その後、利用者がローカルファイルを提供しました。NBA 2K27 の初期ビルドに同版の DLL が含まれたという[報道](https://videocardz.com/newz/nvidia-dlss-5-neural-rendering-dll-found-in-nba-2k27-early-access-build-file-is-3x-larger-than-dlss-4)がありますが、これは現在の配布版への同梱や、別用途での利用権限を保証する資料ではありません。所有している配布物を確認し、DLL の再配布サイトや抽出済み重みのミラーを前提にしないでください。

## 必要ファイルの関係

| ファイル | 入手・生成方法 | 用途と扱い |
|---|---|---|
| `nvngx_dlssnr.dll` | 利用者の正当に入手した x64 / 310.8.0.0 | NVIDIA NR モデルの元ファイル。版の検査では DLL をロードしません |
| `dlssnr_on_amd_setup.exe` | [作者の v0.2.17 リリース](https://github.com/danielblnc/DLSS-NR-on-AMD/releases/tag/v0.2.17)から直接取得 | ローカルセットアップ。GitHub 公表値と検証済み上流値の SHA-256 が一致 |
| `dxgi.dll` 等のプロキシ | 上記セットアップが生成 | このホストでは同じバイト列をプライベート領域の `version.dll` として配置 |
| `dlssnr_on_amd_weights.bin` | セットアップが元 DLL からローカルに生成 | 元 DLL とセットで使用。上流の検証済みサイズ・SHA-256 と照合 |
| `dlss5_video_native.exe` | `upstream.lock.json` の固定ホストをビルド | ComfyUI の画像を D3D12 / HIP 経路へ渡すホスト |
| `dlssnr_on_amd.ini` | セットアップが生成。推論ジョブ用の設定はブリッジが別途生成 | ブリッジは色入力のみ・履歴なしの固定プロファイルを使用 |
| `backend.local.json` | 補助ツールまたは既存の `init-config` | 絶対パス、ファイルハッシュ、HIP 番号、タイムアウトを保存。ワークフローには含めません |

補助ツールのセットアップ、DLL、重み、私的ログは Git の対象外の `local-build/` 内へ保存します。利用者が手動導入した `dlssnr_setup/` も Git の対象外です。ソース ZIP にも収録しません。プロキシのファイル名を揃える際もバイナリは改変しません。

## v0.2.17 を固定する理由

固定ホスト `9303dfaa14c2ca83e237ff18318bdfc0b767f6fb` の [PERFORMANCE.md](https://github.com/eikkapine/DLSS5-AMD-Video/blob/9303dfaa14c2ca83e237ff18318bdfc0b767f6fb/native/PERFORMANCE.md) が、v0.2.17 と色入力のみのファイル処理について実行結果・生成物のハッシュを記録しています。

調査時の最新版は **v0.4.0** です。ただし v0.3 系以降は `Inline` から `Async`、`PreUpscale`、`PreHistory` を使う設定へ変化しており、既存ホストの完了ログ判定も含めて互換性が未検証です。補助ツールは最新版を自動選択しません。最新版のゲーム内 FPS を ComfyUI の処理速度として引用することもできません。

固定値は [`runtime.lock.json`](../runtime.lock.json) に保存しました。

| 対象 | バイト数 | SHA-256 |
|---|---:|---|
| v0.2.17 setup | 7,538,418 | `4fcd167d07bc4964eaf9162aa8f4f11e852b91bf866b28cb48d45934022440bc` |
| 生成プロキシ | 7,248,384 | `bc97f3b06718e19042acaf227bfe15d1e43d4977f9dc2e39994fcc511445ff4e` |
| 生成重み | 147,689,451 | `6bf8dc931ef3ccffe18c82de26ab374156e7f19539ffcf8eabaa25dca5cf15ab` |

ハッシュが違う場合は処理を停止し、設定を発行しません。同じバージョン表示でも生成物が違えば再調査が必要です。ハッシュの一致は画質や GPU 実行の証明ではありません。

## この PC で確認した状態

| 項目 | 結果 |
|---|---|
| GPU / ドライバー | RX 9070 XT / Windows ドライバー `32.0.31041.1004` |
| ComfyUI | 0.37.4、PyTorch `2.13.0+rocm10.0.0`、ComfyUI では RX 9070 XT が `cuda:0` |
| ホスト | MSVC 19.44 でビルド済み。RX 9070 XT 上の D3D12 無効モード往復に成功 |
| 公式 setup | 利用者が手動実行。v0.2.17 setup、生成プロキシ、重みのサイズ・SHA-256 が上記に一致 |
| NVIDIA NR DLL | 利用者提供の x64 / 310.8.0.0、165,840,496 bytes。ロードせずに PE と版を検査 |
| ニューラル推論 | 異なる 640×360 SDR 合成画像 2 枚、CLI、ComfyUI API の処理・PNG 保存に成功 |
| 画質 | 黒崩れと取り違えがないことを目視。画質改善・自然写真・動画の品質は未検証 |

ダウンロードした setup の Authenticode 状態は `NotSigned` でした。GitHub の公開ハッシュと上流記録を照合して出所を記録していますが、発行者署名や実行時の安全性を証明するものではありません。Windows が実行を拒否した場合は、その理由を確認し、セキュリティ設定の変更で自動的に通す処理は行いません。

HIP の番号は PyTorch の番号と異なりました。各 DLL を別プロセスで列挙した結果です。

| システム HIP DLL | index 0 | index 1 |
|---|---|---|
| `amdhip64_6.dll` | 内蔵 Radeon Graphics | RX 9070 XT、PCI `0000:03:00.0` |
| `amdhip64_7.dll` | 内蔵 Radeon Graphics | RX 9070 XT、PCI `0000:03:00.0` |
| 古い `amdhip64.dll` | 内蔵 Radeon Graphics | 検出なし |

この環境は **`hip_device="1"`** で実行成功しました。子プロセスを `HIP_VISIBLE_DEVICES=1` に制限すると、その中では RX 9070 XT が device 0 へ振り直されます。実ログでも `using HIP device 0 ... AMD Radeon RX 9070 XT, arch gfx1201` と D3D12 アダプターの一致を確認しました。システム DLL の置換や、内蔵 GPU の無効化は行っていません。ドライバーの内部バージョンと Adrenalin の製品バージョンは別なので、要求される Adrenalin 26.1.1 以上かの判定を文字列の大小比較だけで行わないでください。

### 手動セットアップの表示について

提供 DLL の SHA-256 は `ceb6432f6fbdf44d886014bcd47241932bf8b67439feef9bbdd0961436662650`。セットアップは既知の DLL 全体ハッシュと異なると表示しましたが、続く検査で **153 テンソルすべてが 310.8.0.0 と一致**し、生成した重みのハッシュも固定値に一致しました。今回は実行完了と生成物検査を確認できているため、この表示だけをインストール失敗とは判断しません。

`No game .exe found` も、オフラインの ComfyUI ホスト用にファイルを生成する用途では問題になりません。ゲーム向け INI の `UseFsrInputs=1`、`UseDepth=1`、`Temporal=1` はそのまま推論に使わず、ブリッジが専用作業フォルダーに色入力のみ・履歴なしの INI を生成します。

### この PC で有効にした設定

検証後に、作業用リポジトリと実 ComfyUI カスタムノードの `config/backend.local.json` を作成しました。どちらも `dlssnr_setup/` の検証済みファイルとビルド済みホストを絶対パス・ハッシュで参照します。**このフォルダーを移動すると設定の更新が必要**です。

通常の待機設定はニューラルジョブ完了後も画像回収条件に達せず、約 80.36 秒で失敗しました。既存ホストの `--fast-isolated` を別の限定試験で実行し、2 枚の完了レポート、入力・出力の対応、GPU ログ、画像を確認してから、この組合せのローカル設定だけ `fast_isolated=true` と `fast_mode_verified_for_these_hashes=true` にしました。ホストの安定画像検査や完了条件は緩めていません。配布設定の初期値は false です。

## 用意できたら実行する手順

標準ライブラリだけで動作する補助ツールなので、ComfyUI の PyTorch 環境を入れ替える必要はありません。以下はリポジトリ直下から実行します。

```powershell
python scripts/setup_runtime.py status
python scripts/setup_runtime.py prepare
python scripts/setup_runtime.py probe-hip --library amdhip64_6.dll
python scripts/setup_runtime.py probe-hip --library amdhip64_7.dll
```

`prepare` は公式 setup の取得と照合だけを行います。既に正しいファイルがあれば再利用します。既存ファイルが違う場合は上書きしません。

NVIDIA DLL を用意できたら、まずロードせずに版と x64 PE ヘッダーを検査します。

自分が正当に入手した ZIP に DLL が入っている場合は、対象の1ファイルだけを一時展開して同じ検査・導入に使えます。重複、危険な ZIP 内パス、512 MiB 超の DLL は拒否します。元 ZIP は変更せず、ほかの内容は展開しません。Git clone からの一括手順は [個人利用セットアップ](PERSONAL_SETUP.md) を参照してください。

```powershell
python scripts/setup_runtime.py status --model-zip 'C:\path\to\your-owned-files.zip'
```

```powershell
$ModelDll = 'C:\path\to\nvngx_dlssnr.dll'
python scripts/setup_runtime.py status --model-dll $ModelDll
```

ローカル利用条件とファイルの出所を確認したうえで、次を実行します。`--enable-config` は確認したローカルファイルを明示的に信頼して設定を有効化する指定です。省略すると無効の設定を作成します。

```powershell
$Comfy = Join-Path $env:USERPROFILE 'Documents\ComfyUI'
$Config = Join-Path $Comfy 'custom_nodes\ComfyUI-DLSS5-AMD\config\backend.local.json'
python scripts/setup_runtime.py install `
  --model-dll $ModelDll `
  --hip-device 1 `
  --accept-runtime-license `
  --enable-config `
  --config-output $Config
```

`--hip-device 1` は上記のローカル列挙結果に基づく値です。他の PC では列挙し直します。`--config-output` を省略すると、このリポジトリの `config/backend.local.json` へ保存します。作業用リポジトリと ComfyUI のカスタムノードが別のコピーの場合、**実際に ComfyUI が読む方の設定パス**を指定してください。

補助ツールは、新規の `local-build/runtime/<日時-ID>/setup/` にセットアップ、元 DLL、ビルド済みホストのコピーを置きます。確認した v0.2.17 の対話入力を送り、120 秒でタイムアウトさせます。生成物をハッシュ照合してから `artifacts/` と新しい設定を発行します。元 DLL、ゲームフォルダー、既存設定は上書きしません。失敗した私的作業フォルダーは調査用に残します。

実行記録 `installation-record.json` は推論未実施であることを明記します。インストールだけでは GPU・画質の合格になりません。

## 1 枚の実機確認とワークフロー

権利のある SDR/sRGB の特徴のある画像を、まず偶数の 640×360 で用意します。設定した ComfyUI の Python を使い、明示的に同じ設定を指定します。

```powershell
$Py = Join-Path $Comfy '.venv\Scripts\python.exe'
& $Py -m amd_nr image 'C:\test\input-sdr.png' 'C:\test\native-001.png' `
  --backend native --config $Config
```

[`04_rx9070xt_native_validation_EXPERIMENTAL.json`](../workflows/04_rx9070xt_native_validation_EXPERIMENTAL.json) を ComfyUI に読み込み、同じ画像を選び直します。成功条件は、実行ログの RX 9070 XT 選択、正常終了、完了レポートのニューラルフレーム数一致、画像の形状・色・内容の確認です。API グラフは[別ファイル](../workflows/04_rx9070xt_native_validation_EXPERIMENTAL.api.json)です。新しい環境では `fast_isolated=false` で開始し、高速化モードは対象の組合せで別途検証してから有効にします。

このファイル処理では色入力のみを使用し、ゲーム側の深度・モーションベクトル・履歴を供給しません。同寸法の処理であり、FSR4 やフレーム生成も実装していません。

## 調査元

- [AMD runtime v0.2.17 README](https://github.com/danielblnc/DLSS-NR-on-AMD/blob/v0.2.17/README.md): DLL 310.8.0.0、対応 GPU、ドライバー、セットアップ手順。
- [AMD runtime LICENSE](https://github.com/danielblnc/DLSS-NR-on-AMD/blob/v0.2.17/LICENSE): 個人・非商用、再配布・商用利用の制限。
- [v0.2.17 release API](https://api.github.com/repos/danielblnc/DLSS-NR-on-AMD/releases/tags/v0.2.17): setup のサイズと GitHub 公表 SHA-256。
- [固定ホストの実行記録](https://github.com/eikkapine/DLSS5-AMD-Video/blob/9303dfaa14c2ca83e237ff18318bdfc0b767f6fb/native/PERFORMANCE.md): setup からの生成、プロキシと重みのハッシュ、速度と限界。
- [当時のセットアップ呼出コード](https://github.com/eikkapine/DLSS5-AMD-Swapper/blob/4272aa371162fc4e094d470ffe5d31e5411436c9/app/Dlss5AmdSwapper/Services/DirectGameInstallerService.cs): 引数なし、専用作業ディレクトリ、対話入力、タイムアウト。
- [現行 Swapper の設定検査](https://github.com/eikkapine/DLSS5-AMD-Swapper/blob/6c20d62c257be52acbc712ddddebd6f6759adeef/app/Dlss5AmdSwapper/Services/DirectGameInstallerService.cs): v0.3 以降の `Async` / `PreUpscale` / `PreHistory`。
- [確認した NVIDIA 公開 SDK](https://github.com/NVIDIA/DLSS/tree/374959484e79a640feaba44c93ac8cfb0a03f5b5/lib/Windows_x86_64): SR/RR/FG DLL は存在し、NR DLL は見つからず。
- [ComfyUI 対応要望 #105](https://github.com/danielblnc/DLSS-NR-on-AMD/issues/105): 要望があることを確認。公式の ComfyUI 対応済みを示す資料ではありません。

セットアップ制御の **17 件のテストが成功**しました。合成ファイルでダウンロード不整合、異なるモデル版、生成物不整合、既存設定の保護を確認し、実 Python 子プロセスで対話入力とタイムアウト時の停止を確認しています。テスト成功と実 runtime の実行成功は別の記録として扱います。

```powershell
python -m unittest discover -s tests -p test_runtime_setup.py -v
```
