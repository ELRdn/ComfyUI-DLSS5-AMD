# ComfyUI-DLSS5-AMD · Experimental Bridge

[English](README.md) | [日本語](README.jp.md)

**Experimental v0.1.0a1 · Validation updated 2026-09-27**

An experimental ComfyUI custom node for Windows / RX 9070 XT that connects to a locally built external AMD neural-rendering host. **Enabled neural processing was verified locally on 2026-09-26; integrated image and three-frame video upscaling through AMD AMF VideoSR1.1 was verified through the ComfyUI API on 2026-09-27.** This repository does not include DLSS weights, DLLs, or a prebuilt GPU host. New installations, natural-image quality, and long videos have not been validated.

This is not an official NVIDIA or AMD product. “DLSS” in the name identifies the technology being investigated; it does not imply affiliation or endorsement.

[Original 2026-09-25 research report (offline HTML)](REPORT.html) · [Japanese source](REPORT_ja.md)

## How to start (personal use)

1. Use Windows x64 with an RX 9070 XT and an existing ComfyUI installation. For the first native build, open an **x64 Visual Studio Developer PowerShell** with Git, CMake, MSVC, NMake, and the Windows SDK. Have a legitimately obtained `nvngx_dlssnr.dll` **310.8.0.0** or a ZIP containing exactly one copy. For the combined image/video nodes, also obtain a Windows `ffmpeg.exe` with `sr_amf` and AMF hardware acceleration. Read the [personal-use setup and source links](docs/PERSONAL_SETUP.md) and the [external runtime license](https://github.com/danielblnc/DLSS-NR-on-AMD/blob/v0.2.17/LICENSE) before proceeding.
2. Clone into the **actual** ComfyUI `custom_nodes` folder. Replace the example paths with yours; point `$Py` to the Python used by ComfyUI.

   ```powershell
   $Comfy = 'C:\path\to\ComfyUI'
   $Py = 'C:\path\to\ComfyUI\.venv\Scripts\python.exe'
   $OwnedZip = 'C:\path\to\your-owned-files.zip'
   $AmfFfmpeg = 'C:\path\to\AMF-enabled\ffmpeg.exe'
   Set-Location (Join-Path $Comfy 'custom_nodes')
   git clone https://github.com/ELRdn/ComfyUI-DLSS5-AMD.git
   Set-Location .\ComfyUI-DLSS5-AMD
   & .\scripts\setup_personal.ps1 -Python $Py -ModelZip $OwnedZip -FFmpeg $AmfFfmpeg -AcceptRuntimeLicense
   ```

   Supply `-ModelDll 'C:\path\to\nvngx_dlssnr.dll'` instead of `-ModelZip` if you have the DLL itself. The script refuses an existing configuration. It verifies local artifacts but does not establish GPU inference or image quality on a new PC. See the [detailed guide](docs/PERSONAL_SETUP.md) if the build, HIP device selection, or AMF check stops.
3. Restart ComfyUI. For an image, put a small **SDR/sRGB** file in ComfyUI's `input` folder or upload it through Load Image. Open [workflow 06](workflows/06_nr_amf_image_ONE_NODE_EXPERIMENTAL.json), select that image in Load Image, start with `factor=2`, then queue the graph. Save Image writes the result to ComfyUI's output folder. For a video, put a short **SDR/CFR** clip directly in ComfyUI's `input` folder, open [workflow 07](workflows/07_nr_amf_video_ONE_NODE_EXPERIMENTAL.json), select that filename, set `max_frames` to cover the clip, and queue it. The lossless MKV is written under `output/amd_nr/`; the node also returns its path. The video node does not include a player UI.

Workflows 06/07 use **native NR at the original size, then AMD AMF VideoSR1.1 for enlargement**. They do not need the separate ComfyUI AMD Video Upscaler custom node. Their UI JSONs passed structural checks; the matching API graphs were executed. Manual browser execution of these two workflows remains unverified. This is a personal, non-commercial research path, not a production-quality or commercially licensed DLSS 5 release.

## Start here

| Goal | File |
|---|---|
| Clone, runtime prerequisites, and source links | [docs/PERSONAL_SETUP.md](docs/PERSONAL_SETUP.md) (Japanese) |
| Original 2026-09-25 research snapshot | [REPORT_ja.md](REPORT_ja.md) (Japanese) |
| Roadmap with acceptance criteria | [ROADMAP.md](ROADMAP.md) (Japanese) |
| Windows / ComfyUI setup | [docs/WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md) (Japanese) |
| Runtime files, acquisition, and setup helper | [docs/RUNTIME_SETUP_ja.md](docs/RUNTIME_SETUP_ja.md) (Japanese) |
| Validation scope and the initial 2026-09-25 test snapshot | [docs/TESTING.md](docs/TESTING.md), [evidence/test-summary.json](evidence/test-summary.json) |
| Handoff for the next development agent | [docs/HANDOFF.md](docs/HANDOFF.md) (Japanese) |

## What is implemented

The bridge validates a ComfyUI `IMAGE`, sends it as an RGBA8 file to an external native host, checks the completion report and output dimensions, then returns an `IMAGE`. On failure, it does not report ordinary resizing or a copy of the input as a successful DLSS result.

| Node | Purpose |
|---|---|
| `AMDNRSettings` | Output compositing mix; it is not an internal model strength or scale factor |
| `AMDNRApply` | Experimental native connection; requires prior configuration of the executable and DLL |
| `AMDNRRenderUpscale` | One image node: native NR at input size, then AMD AMF VideoSR1.1 at 2–8× |
| `AMDNRRoundtrip` | CPU input/output diagnostic only. **Not DLSS** |
| `AMDNRResize` | Ordinary bicubic resize. **Not DLSS or FSR** |
| `AMDNRCompare` | Side-by-side source/result comparison and pixel difference; not an image-quality score |
| `AMDNRDiagnostics` | Python / PyTorch / FFmpeg / configuration diagnostics; does not load the DLL |
| `AMDNRVideoFile` | Processes short SDR/CFR video from an input folder and writes lossless FFV1/MKV |
| `AMDNRVideoUpscaleFile` | One video node: per-frame NR, then VideoSR1.1; writes lossless MKV with copied audio |

JSON records frame counts, hashes, runtime, and failure reasons. Video processing bounds RAM use by chunk, but stores intermediate data for the entire video on disk. It is not a full-movie streaming implementation.

## Implementation and validation boundaries

**Implemented:** Python nodes, CLI, external host bridge, configuration and SHA-256 checks, image/video processing, timeouts, cancellation, overwrite protection, tests, and example workflows.

**CPU-validated:** node imports and methods, image roundtrip, the native I/O contract with an explicit test double, and pixel, frame-order, and audio-payload roundtrips using real FFmpeg.

**Local Windows checks (2026-09-26):** the pinned host and v0.2.17 runtime completed two distinct 640×360 SDR frames on the RX 9070 XT, followed by CLI and native ComfyUI image processing. The ComfyUI API workflow saved a native PNG and an original/result comparison. The locally verified configuration uses `fast_isolated=true`; conservative pacing failed the unchanged capture gate. See the [validation record](docs/RX9070XT_VALIDATION_2026-09-26.md).

**Not validated:** image-quality improvement, natural-photo quality, sustained video processing, general performance, or peak VRAM use. The synthetic-image and three-frame video tests establish execution, scaling dimensions, and file/audio output only.

## Check without a GPU

Run these from the repository root in an existing, suitable Python environment:

```powershell
python -m amd_nr doctor
python -m amd_nr selftest --output selftest-output
```

`selftest-output/reference_NOT_DLSS.png` checks the I/O path. It is not a neural-processing result.

To run development tests, use the commands below. **Do not replace ComfyUI's GPU-enabled PyTorch with a CPU build.** This repository's requirements do not install PyTorch.

```powershell
python -m pip install -r requirements.txt
python -m pip install pytest coverage
python scripts/collect_evidence.py
```

Node-method tests require an existing PyTorch installation. Check whether the terminal's `python` is the same Python used by ComfyUI.

## Native setup

The [guided setup](docs/PERSONAL_SETUP.md) fetches the pinned author's **v0.2.17** installer, builds the pinned external host locally, checks hashes, and creates a private configuration. It never downloads the NVIDIA NR DLL. The [manual Windows steps](docs/WINDOWS_SETUP.md) and [runtime analysis](docs/RUNTIME_SETUP_ja.md) explain each stage. ROCm, the author's AMD NR runtime, and AMF VideoSR1.1 are separate components; installing ROCm does not supply the NR proxy, weights, or NVIDIA DLL. External runtime and model terms remain separate from this repository's MIT license.

## ComfyUI

Place this entire folder at `ComfyUI/custom_nodes/ComfyUI-DLSS5-AMD/` and restart ComfyUI.

- `workflows/01_cpu_transport_NOT_DLSS.json`: CPU diagnostic.
- `workflows/02_native_image_EXPERIMENTAL.json`: native processing and A/B comparison.
- `workflows/03_native_video_EXPERIMENTAL.json`: short-video file processing.
- `workflows/04_rx9070xt_native_validation_EXPERIMENTAL.json`: native image validation with diagnostics; requires the local runtime. Locally exercised at 640×360 SDR.
- `workflows/05_rx9070xt_nr_then_amf_sr_EXPERIMENTAL.json`: NR followed by a **separate AMD AMF VideoSR1.1** node. Requires the external ComfyUI AMD Video Upscaler and AMF-enabled FFmpeg; defaults to 2×. See the [scaling check](docs/SCALING_VALIDATION_2026-09-27.md).
- `workflows/06_nr_amf_image_ONE_NODE_EXPERIMENTAL.json`: image NR + VideoSR1.1 in this custom node, with no second plugin node.
- `workflows/07_nr_amf_video_ONE_NODE_EXPERIMENTAL.json`: short SDR/CFR video NR + VideoSR1.1, preserving copied audio.

Matching `.api.json` files are API graph forms. Load the JSON files without `.api` in the regular UI, then reselect the Load Image image or video file. Workflow 04 was opened and run in the browser; workflows 05–07 were run through ComfyUI's API and structurally checked as UI graphs. For 06/07, pin an AMF-enabled FFmpeg in the server's private config with `python scripts/setup_runtime.py configure-amf --ffmpeg C:\path\to\ffmpeg.exe --config config\backend.local.json` before restarting ComfyUI. See [Windows setup](docs/WINDOWS_SETUP.md).

## Important limits

The native NR stage supports **SDR, RGBA8 transport, no temporal history, and unchanged dimensions**. The default native acceptance range is at most 1920 pixels wide and 1080 pixels high, with even dimensions of at least 16. Combined nodes scale only after that stage and limit output edges to 8192 pixels. A portrait image 1280 pixels high or a 4K image is not automatically downscaled before NR.

A Load Image `MASK` may have inverted meaning because it derives from transparency. This node's `effect_mask` uses **white = apply effect**. Check the mask semantics before connecting them directly.

For scaling, workflows 06/07 run native NR and AMD AMF VideoSR1.1 inside one node each. On this RX 9070 XT, a synthetic image completed at 8× from 640×360 and 4× from 1920×1080 in short probes. The integrated image and three-frame video paths passed at 2×. This does not establish a usable-quality limit or implement DLSS super-resolution. `AMDNRResize` is only a bicubic control. FSR4 is not implemented.

## License and privacy

Original code in this repository is MIT-licensed. External runtimes, weights, NVIDIA DLLs, and other projects have separate licenses. The MIT label on this code does not grant distribution rights to models. See [LICENSE](LICENSE), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and [SECURITY.md](SECURITY.md).

Routine processing does not send data over the network. Logs may contain local paths. `--keep-debug-files` retains copies of images, DLLs, and weights; do not publish or upload them.
