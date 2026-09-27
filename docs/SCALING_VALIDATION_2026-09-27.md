# RX 9070 XT scaling check · 2026-09-27

## What was tested

This bridge's native `AMDNRApply` performs color-only neural rendering **at the input dimensions**. It has no super-resolution output or scale factor. Scaling below uses the separately installed [ComfyUI AMD Video Upscaler](https://github.com/Yasei-no-otoko/ComfyUI-AMD-Video-Upscaler) node after NR. Its FFmpeg `sr_amf` path is AMD AMF, not DLSS super-resolution. FFmpeg debug output identifies `sr1-0` as FSR1.0 and `sr1-1` as VideoSR1.1. The delivered workflow selects VideoSR1.1 with fallback set to `error`.

The local FFmpeg 9.0 full build exposes `sr_amf`, `vpp_amf`, and AMF hardware acceleration. Its debug log selected D3D11 device ID `0x7550`; the Windows video-controller record maps `DEV_7550` to this machine's **RX 9070 XT**. The other integrated Radeon is `DEV_164E`.

## Results

The input is the synthetic 640×360 SDR test card used for the prior native check. A new enabled NR run produced one neural frame (`job-gll62tsx`, bridge time 3.343 s). For higher native input sizes, that test card was resized with bicubic **before** NR; those cases test execution and dimensions, not detail recovery.

| Stage / input | Tested output | Result |
|---|---|---|
| NR 640×360 | 640×360 | Enabled neural completion; unchanged dimensions |
| NR 960×540 | 960×540 | Enabled neural completion; 3.484 s bridge time |
| NR 1280×720 | 1280×720 | Enabled neural completion; 3.500 s bridge time |
| NR 1920×1080 | 1920×1080 | Enabled neural completion; 3.734 s bridge time |
| VideoSR1.1 after 640×360 NR | 2× 1280×720, 3× 1920×1080, 4× 2560×1440, 6× 3840×2160, 8× 5120×2880 | All sizes passed twice; same raw RGB hash on both runs per size |
| VideoSR1.1 after 1920×1080 NR | 2× 3840×2160, 3× 5760×3240, 4× 7680×4320 | All sizes passed twice; same raw RGB hash on both runs per size |

The 640×360 matrix also passed twice per size with `sr1-0`/FSR1.0. The VideoSR1.1 probe calls took 0.34–2.05 s from 640×360 and 1.10–5.05 s from 1920×1080, including Python transfer and FFmpeg process startup. Some first runs also saved a PNG inside that timing; the calls exclude the NR stage and ComfyUI queue. Each run checked exact output dimensions, non-collapsed mean RGB, completion without fallback, and raw RGB SHA-256. Two matching runs are a short reproducibility check, not a long-term stability claim.

The paired [UI workflow](../workflows/05_rx9070xt_nr_then_amf_sr_EXPERIMENTAL.json) and [API graph](../workflows/05_rx9070xt_nr_then_amf_sr_EXPERIMENTAL.api.json) connect `LoadImage → AMDNRApply → AMDAMFVideoUpscale → SaveImage`, retaining the NR and A/B saves. In an isolated ComfyUI server, the VideoSR1.1 graph completed at 2× and 4× and saved 1280×720 and 2560×1440 PNGs. The initial FSR1.0 graph execution included an uncached NR run; the later VideoSR1.1 graph executions reused that NR result through ComfyUI's cache and executed the AMF node anew. The UI JSON was structurally checked, while the actual graph execution was via API.

## Practical reading

For the tested synthetic frame, **8× from 360p** and **4× from 1080p** are the largest completed outputs. This is an operational range for one image and this FFmpeg/driver combination, not a maximum supported factor. The Advanced node allows up to 8×; 1080p→6×/8× was not exercised. The `AMDNRApply` input envelope remains at most 1920×1080 in the local configuration; larger outputs occur only after NR.

At higher factors, the displayed image grows but its real source detail is still limited by the original. There was no natural-photo reference, high-resolution ground truth, face/text fidelity score, video continuity check, extended repetition, or peak VRAM measurement. **A usable-quality maximum cannot be inferred from this test.** Start a real-image review at 2×, compare with 4× at the intended display size, and treat 6×/8× as experimentally executable. Keep `fallback_policy=error` so a CPU or ordinary resize cannot be mistaken for an AMF result.

The portable workflow uses `ffmpeg` as its executable name. This PC's default PATH resolves to an FFmpeg build without AMF filters; select the installed FFmpeg 9.0 full build in the Advanced node before running. A personalized workflow named `AMDNR_RX9070XT_AMF_SR_2倍.json` is saved in the local ComfyUI workflows folder with the AMF-enabled path and test image already selected. The external node, FFmpeg build, and local NR runtime must be present.

Private raw results and the probe scripts are under ignored `local-build/scaling-validation/`. Source NR manifests are `runs/native/job-gll62tsx`, `job-vabt3xuw`, `job-_m04edtm`, and `job-mwn63bqa`. The VideoSR1.1 ComfyUI API prompts are `a3a0bb49-e2f5-436b-bdf1-f16d4f4b5057` (2×) and `08da0ac5-d4b6-4d43-b1ea-2de43cd28d23` (4×). Runtime binaries and weights are not included in the source workflow.

## Integrated image and video nodes

The custom node now includes `AMDNRRenderUpscale` (image) and `AMDNRVideoUpscaleFile` (video). Each takes the scale factor and mix on one node, runs native NR at the source dimensions, and invokes pinned FFmpeg AMF VideoSR1.1 itself. The FFmpeg path and SHA-256 are held in the private server config as `amf_ffmpeg`; neither path nor runtime files are workflow inputs. This PC also pins `amf_expected_device_id=7550`, so a different or unidentified AMF GPU is rejected. A missing or changed AMF executable fails before neural work or output publication. The VideoSR1.1 completion log and exact raw output byte count are checked, with no resize fallback.

The isolated ComfyUI server loaded **only this custom node** and executed the paired [one-node image workflow](../workflows/06_nr_amf_image_ONE_NODE_EXPERIMENTAL.json) and [one-node video workflow](../workflows/07_nr_amf_video_ONE_NODE_EXPERIMENTAL.json) through the API. Prompt `5c4fd75e-416e-4b0e-bd5a-571b6030ca50` saved a 1280×720 PNG from a 640×360 synthetic image. Prompt `7883453a-263a-4a5f-8cb9-94cd25d39811` saved a 1280×720 lossless MKV from a three-frame, 24 fps, 640×360 source with one audio stream. All three video frames reported neural completion and AMF device ID `7550` (RX 9070 XT). The output had three frames, the same 24 fps and one audio stream; copied audio packet-payload hashes matched, and the published file matched its manifest SHA-256. The video node's graph time was 17.229 s for three frames. Audio timestamp alignment was not independently verified.

The new UI JSONs passed structural checks; browser opening and button execution remain untested. Unit checks cover the fail-closed missing-AMF gate, frame order and audio preservation with a clearly labelled test scaler, and no publication after an upscale failure. The real three-frame result is additional hardware evidence. Natural footage, longer clips, temporal consistency, and playback sync remain for quality validation.

The built-in image node additionally completed 640×360→5120×2880 at 8× with one new enabled neural frame and the expected `7550` AMF device. A three-frame clip also completed at 2× with `chunk_frames=2`; its frame count, audio payload, and output dimensions matched. These are short execution checks only.

After the GPU device pin was installed in the normal ComfyUI custom-node copy, a fresh isolated server ran the image and video workflows again with **no cached nodes**: prompt `f29f7c4f-4e63-4ebd-b468-a1ef97887cd2` saved the 1280×720 PNG in 5.092 s; prompt `efd86cc9-0996-4d81-80af-560e97606f99` saved the 1280×720 MKV in 13.299 s. The three decoded output frames have distinct RGB hashes. All three report neural completion and AMF device `7550`; the video audio payload and published file hash match their checks.
