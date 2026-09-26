# ComfyUI-DLSS5-AMD · Experimental Bridge

[English](README.md) | [日本語](README.jp.md)

**Version 0.1.0a1 · Research snapshot: 2026-09-25**

An experimental ComfyUI custom node for Windows / RX 9070 XT that connects to an AMD neural-rendering host supplied by the user. **This repository does not include DLSS weights, DLLs, or a finished GPU engine. GPU inference was not run in the development environment.**

This is not an official NVIDIA or AMD product. “DLSS” in the name identifies the technology being investigated; it does not imply affiliation or endorsement.

[Full research report (offline HTML)](REPORT.html) · [Japanese research report](REPORT_ja.md)

## Start here

| Goal | File |
|---|---|
| Research findings and technical decisions | [REPORT_ja.md](REPORT_ja.md) (Japanese) |
| Roadmap with acceptance criteria | [ROADMAP.md](ROADMAP.md) (Japanese) |
| Windows / ComfyUI setup | [docs/WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md) (Japanese) |
| Test results and remaining validation | [evidence/test-summary.json](evidence/test-summary.json), [docs/TESTING.md](docs/TESTING.md) |
| Handoff for the next development agent | [docs/HANDOFF.md](docs/HANDOFF.md) (Japanese) |

## What is implemented

The bridge validates a ComfyUI `IMAGE`, sends it as an RGBA8 file to an external native host, checks the completion report and output dimensions, then returns an `IMAGE`. On failure, it does not report ordinary resizing or a copy of the input as a successful DLSS result.

| Node | Purpose |
|---|---|
| `AMDNRSettings` | Output compositing mix; it is not an internal model strength or scale factor |
| `AMDNRApply` | Experimental native connection; requires prior configuration of the executable and DLL |
| `AMDNRRoundtrip` | CPU input/output diagnostic only. **Not DLSS** |
| `AMDNRResize` | Ordinary bicubic resize. **Not DLSS or FSR** |
| `AMDNRCompare` | Side-by-side source/result comparison and pixel difference; not an image-quality score |
| `AMDNRDiagnostics` | Python / PyTorch / FFmpeg / configuration diagnostics; does not load the DLL |
| `AMDNRVideoFile` | Processes short SDR/CFR video from an input folder and writes lossless FFV1/MKV |

JSON records frame counts, hashes, runtime, and failure reasons. Video processing bounds RAM use by chunk, but stores intermediate data for the entire video on disk. It is not a full-movie streaming implementation.

## Implementation and validation boundaries

**Implemented:** Python nodes, CLI, external host bridge, configuration and SHA-256 checks, image/video processing, timeouts, cancellation, overwrite protection, tests, and example workflows.

**CPU-validated:** node imports and methods, image roundtrip, the native I/O contract with an explicit test double, and pixel, frame-order, and audio-payload roundtrips using real FFmpeg.

**Not validated:** a Windows native build, inference on an RX 9070 XT, operation in a real ComfyUI server and browser, image-quality improvement, GPU speed, or VRAM use. Passing automated tests does not establish any of these.

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

Follow the [Windows setup guide](docs/WINDOWS_SETUP.md) (Japanese) to fetch, inspect, and build the external host at a pinned revision, then configure a local runtime you are authorized to use. Review the external host code before running it.

```powershell
python scripts/fetch_upstream.py
# Then, in an x64 Visual Studio Developer PowerShell:
.\scripts\build_native.ps1 -Python python
```

This **only builds the host**. It does not obtain weights or a runtime, or change drivers. Use `init-config` to generate hashes for the runtime configuration, then review and enable that configuration manually. See the setup guide for details.

## ComfyUI

Place this entire folder at `ComfyUI/custom_nodes/ComfyUI-DLSS5-AMD/` and restart ComfyUI.

- `workflows/01_cpu_transport_NOT_DLSS.json`: CPU diagnostic.
- `workflows/02_native_image_EXPERIMENTAL.json`: native processing and A/B comparison.
- `workflows/03_native_video_EXPERIMENTAL.json`: short-video file processing.

Matching `.api.json` files are API graph forms. Load the JSON files without `.api` in the regular UI, then reselect the Load Image image or video file. These workflows passed structural checks, but have not been run in a browser.

## Important limits

The first release supports **SDR, RGBA8 transport, no temporal history, and unchanged dimensions**. The default native acceptance range is at most 1920 pixels wide and 1080 pixels high, with even dimensions of at least 16. A portrait image 1280 pixels high or a 4K image is not automatically downscaled. Explicit preprocessing or a configuration change after hardware validation is required.

A Load Image `MASK` may have inverted meaning because it derives from transparency. This node's `effect_mask` uses **white = apply effect**. Check the mask semantics before connecting them directly.

If actual upscaling is the goal, connect a ComfyUI super-resolution node as a separate step after NR has passed image-quality evaluation. `AMDNRResize` is only a bicubic control. FSR4 is not implemented.

## License and privacy

Original code in this repository is MIT-licensed. External runtimes, weights, NVIDIA DLLs, and other projects have separate licenses. The MIT label on this code does not grant distribution rights to models. See [LICENSE](LICENSE), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and [SECURITY.md](SECURITY.md).

Routine processing does not send data over the network. Logs may contain local paths. `--keep-debug-files` retains copies of images, DLLs, and weights; do not publish or upload them.
