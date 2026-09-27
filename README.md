# ComfyUI-DLSS5-AMD · Experimental Bridge

[English](README.md) | [日本語](README.jp.md)

**Version 0.1.0a1 · Research snapshot: 2026-09-25**

An experimental ComfyUI custom node for Windows / RX 9070 XT that connects to an AMD neural-rendering host supplied by the user. **Enabled neural processing was verified locally on 2026-09-26; integrated image and three-frame video upscaling through AMD AMF VideoSR1.1 was verified through the ComfyUI API on 2026-09-27.** This repository does not include DLSS weights, DLLs, or a finished GPU engine.

This is not an official NVIDIA or AMD product. “DLSS” in the name identifies the technology being investigated; it does not imply affiliation or endorsement.

[Full research report (offline HTML)](REPORT.html) · [Japanese research report](REPORT_ja.md)

## Start here

| Goal | File |
|---|---|
| Research findings and technical decisions | [REPORT_ja.md](REPORT_ja.md) (Japanese) |
| Roadmap with acceptance criteria | [ROADMAP.md](ROADMAP.md) (Japanese) |
| Windows / ComfyUI setup | [docs/WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md) (Japanese) |
| Runtime files, acquisition, and setup helper | [docs/RUNTIME_SETUP_ja.md](docs/RUNTIME_SETUP_ja.md) (Japanese) |
| Test results and remaining validation | [evidence/test-summary.json](evidence/test-summary.json), [docs/TESTING.md](docs/TESTING.md) |
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

For a personal-use Windows install from a clone, use the [guided ZIP setup](docs/PERSONAL_SETUP.md). It accepts your own legitimately obtained ZIP containing one `nvngx_dlssnr.dll` (or the DLL itself), fetches the pinned public installer, builds the pinned host, verifies generated files, and writes a private ComfyUI configuration. An AMF-capable FFmpeg executable can be supplied for the integrated image/video upscale nodes. The runtime's license excludes commercial use and bundling; a paid customer distribution needs separate permission from its author.

Follow the [Windows setup guide](docs/WINDOWS_SETUP.md) (Japanese) to fetch, inspect, and build the external host at a pinned revision, then configure a local runtime you are authorized to use. Review the external host code before running it.

```powershell
python scripts/fetch_upstream.py
# Then, in an x64 Visual Studio Developer PowerShell:
.\scripts\build_native.ps1 -Python python
```

This **only builds the host**. It does not obtain weights or a runtime, or change drivers. Use `init-config` to generate hashes for the runtime configuration, then review and enable that configuration manually. See the setup guide for details.

The optional setup helper downloads the pinned **v0.2.17** installer directly from its author's release and verifies its SHA-256:

```powershell
python scripts/setup_runtime.py prepare
python scripts/setup_runtime.py status
```

Installation requires your legitimately obtained **`nvngx_dlssnr.dll` 310.8.0.0 (x64)**. The external installer generates the AMD proxy and weights locally; the helper verifies their pinned hashes before writing a new configuration. See the [runtime setup guide](docs/RUNTIME_SETUP_ja.md) for HIP device selection and the `install` command. The AMD runtime permits personal, non-commercial use and prohibits redistribution. Newer runtime versions are not validated with this host.

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
