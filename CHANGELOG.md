# Changelog

## Unreleased — 2026-09-27

Documented the user-reported unofficial Streamline ZIP provenance: its issue lists the same NR DLL SHA-256 as the locally supplied file, whose Authenticode status is `HashMismatch`. The rolling third-party archive is not an automatic download source or a verified redistribution grant.

Added a personal-use setup path for a fresh Git clone. A user-supplied ZIP can provide exactly one `nvngx_dlssnr.dll`; only that entry is temporarily extracted, inspected, and removed after installation. `scripts/setup_personal.ps1` verifies or fetches the pinned host, builds it, selects a consistent RX 9070 XT HIP index, downloads the pinned author's installer, and writes a new private configuration. Optional AMF FFmpeg configuration supports the integrated upscaling nodes. The runtime and NVIDIA DLL are still not redistributed, and the third-party runtime's license remains personal/non-commercial.

The setup guide now links directly to the original host/runtime sources, the FFmpeg download pages, and the external AMF node used by the old comparison workflow. It distinguishes ROCm, the separate AMD NR runtime, and the AMF VideoSR1.1 stage; the integrated 06/07 workflows do not require the external AMF custom node.

Added `AMDNRRenderUpscale` and `AMDNRVideoUpscaleFile` so each ComfyUI workflow needs one processing node for native NR followed by AMD AMF VideoSR1.1. The AMF-enabled FFmpeg executable is SHA-256-pinned in private server configuration; no executable path or CPU fallback is exposed to workflows. Video output remains lossless FFV1/MKV with copied, payload-checked audio.

On RX 9070 XT, the integrated image node saved a 640×360→1280×720 PNG and the integrated video node saved a three-frame, 24 fps 640×360→1280×720 MKV with matching audio payloads. The new UI/API workflows are 06 and 07. This verifies short execution, not natural-image quality, sustained video, temporal NR, or game integration.

## Unreleased — 2026-09-26

Added a pinned v0.2.17 runtime setup helper, DLL version inspection, HIP device
enumeration, installer/output hash checks, exclusive configuration creation, and
17 setup tests. Added the runtime acquisition guide and an experimental RX 9070 XT
workflow with diagnostics. The verified installer is cached locally and excluded
from distribution. Installation still requires the user's NVIDIA NR DLL 310.8.0.0.

The user subsequently supplied and installed the matching runtime. Exact installer,
proxy, weights, and model-version checks passed. Two distinct 640×360 SDR frames,
the image CLI, and the native ComfyUI API workflow completed on RX 9070 XT.
Conservative pacing failed its capture gate; the existing fast-isolated path
passed with the completion checks unchanged and was enabled only in local configs.
Renamed workflow 04 from UNVERIFIED to EXPERIMENTAL and recorded the bounded results.
Image-quality improvement remains unverified. The external AMD runtime is for
personal, non-commercial use. Private setup files are excluded from Git.

## 0.1.0a1 — 2026-09-25

Initial research/implementation delivery, not a hardware-tested release.

Added seven classic ComfyUI node classes, standalone image/video/config/doctor CLI,
explicitly labelled CPU transport reference, pinned-contract native adapter,
SHA-256-gated server configuration, strict native completion validation,
mask/mix/alpha handling, subprocess cancellation, private job manifests,
lossless short-video processing, source-fetch/build helpers and sample workflows.

Added CPU/unit/contract and real FFmpeg tests, reproducible evidence collection,
source inventory, Japanese report, acceptance-gated roadmap and Windows handoff.

Not included/tested: GPU runtime or weights, Windows native build, RX 9070 XT
inference, full ComfyUI server/browser execution, temporal NR, FSR4, direct HIP,
ONNX provider, zero-copy, sustained performance/quality claims.
