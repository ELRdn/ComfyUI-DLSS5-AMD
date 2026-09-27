# RX 9070 XT local validation · 2026-09-26

**Result: enabled neural processing and ComfyUI PNG output passed at 640×360 SDR.** This is a bounded execution test using synthetic images, not proof of improved image quality or a general DLSS 5 compatibility claim.

The user supplied `nvngx_dlssnr.dll` and ran the v0.2.17 installer in the private `dlssnr_setup/` folder. The missing-file blocker is resolved. The setup helper's automatic `install` success path was not exercised; existing generated artifacts were verified and reused.

## Verified artifacts

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| v0.2.17 installer | 7,538,418 | `4fcd167d07bc4964eaf9162aa8f4f11e852b91bf866b28cb48d45934022440bc` |
| `version.dll` | 7,248,384 | `bc97f3b06718e19042acaf227bfe15d1e43d4977f9dc2e39994fcc511445ff4e` |
| `dlssnr_on_amd_weights.bin` | 147,689,451 | `6bf8dc931ef3ccffe18c82de26ab374156e7f19539ffcf8eabaa25dca5cf15ab` |
| `nvngx_dlssnr.dll` | 165,840,496 | `ceb6432f6fbdf44d886014bcd47241932bf8b67439feef9bbdd0961436662650` |
| Locally built native host | 184,832 | `a864a4cd3d04876a4483565091be0ee92619b8612bcb9272859ecf04437f2dae` |

The installer, proxy and weights match [`runtime.lock.json`](../runtime.lock.json). The model has an x64 DLL PE header and FileVersion `310.8.0.0`; inspection did not execute it. The user's installer transcript reports an unfamiliar whole-DLL hash followed by all 153 tensors matching. The generated weights match the pinned hash exactly.

The host was built with MSVC 19.44 from `eikkapine/DLSS5-AMD-Video` commit `9303dfaa14c2ca83e237ff18318bdfc0b767f6fb`; its source checks and build record passed. The signed-script policy blocked the PowerShell build wrapper, so its inspected CMake commands were run under the Visual Studio x64 environment. No execution-policy change was made.

## Machine and GPU selection

- Windows build 26200; RX 9070 XT driver `32.0.31041.1004`.
- ComfyUI `0.37.4`, frontend `1.52.7`, Python `3.12.9`, PyTorch `2.13.0+rocm10.0.0`, HIP build `7.15.26333`.
- ComfyUI reports `cuda:0 AMD Radeon RX 9070 XT : native`.
- System HIP 6/7 enumeration reports integrated Radeon at index 0 and RX 9070 XT at index 1, PCI `0000:03:00.0`.
- Native children receive `HIP_VISIBLE_DEVICES=1`. Within that filtered process, the RX 9070 XT becomes HIP device **0**. The runtime log explicitly selects it, architecture `gfx1201`, matching the D3D12 adapter.
- Runtime log: inline, zero-copy, history off; HIP runtime/driver integer `70260201`.

GPU identity and completion are corroborated by host/runtime logs. The bridge's `independent_gpu_verification=false` remains correct: these records are not an independent hardware profiler or cryptographic attestation.

## Executed checks

| Check | Result | Time |
|---|---|---:|
| Earlier disabled D3D12 roundtrip | RX 9070 XT; 64×48 bytes identical; 0 neural frames | Diagnostic only |
| Conservative pacing, enabled | Failed capture gate; no PNG published | 80.359 s |
| Existing `--fast-isolated`, two distinct 640×360 inputs | 2 input / 2 output / 2 neural frames; 4 logged completions | 5.781 s |
| Image CLI using the verified fast config | 1 input / 1 output / 1 neural frame; 2 logged completions; PNG saved | 3.766 s bridge time |
| Native ComfyUI API workflow 04 | Successful uncached execution; native PNG and A/B PNG saved | 6.603 s graph time; 4.984 s bridge time |

The synthetic test card contains gradients, noise, fine lines, text, shapes and color patches. The second input mirrors it and permutes RGB channels. For each isolated worker, raw input equals its intended source and concatenated output equals the worker's result. The two outputs differ. Alpha remains 255. RGB mean absolute changes are 2.963/255 and 2.418/255, with brightness ratios 1.00155 and 1.00170. These are difference checks, not quality scores.

Actual images were inspected: no near-black collapse or frame substitution was seen. Fine texture and tone change, but synthetic patterns cannot establish natural-photo improvement, face fidelity or preservation of meaning. Small differences also occur across repeated native executions; bitwise determinism is not promised.

### Conservative pacing failure and local configuration

The first run logged neural jobs on the intended GPU and produced a plausible diagnostic capture, but exhausted 1,200 feeds without satisfying the host's unchanged acceptance condition, including two consecutive identical captures. It returned `ISOLATED_COMPLETION_TIMEOUT`. No successful image was published from this failed run.

The already implemented `--fast-isolated` mode was then tested in a fresh private workspace with two distinct inputs. It passed the same completion, stability and collapse checks. Only after that inspection were `fast_isolated=true` and `fast_mode_verified_for_these_hashes=true` enabled in the two local configs. No host source, completion rule, runtime binary or distributed default was changed. This does not prove why conservative pacing failed or establish performance outside this input size.

## ComfyUI workflow and outputs

The [UI workflow](../workflows/04_rx9070xt_native_validation_EXPERIMENTAL.json) and paired [API graph](../workflows/04_rx9070xt_native_validation_EXPERIMENTAL.api.json) contain LoadImage, Settings, Native Render, A/B Compare, two SaveImage nodes and Diagnostics. Reselect a local SDR image when using the portable workflow. `mix=1` was used for validation.

The installed ComfyUI node's config references the verified files in this working repository. Moving `dlssnr_setup/` or the native host requires reviewing and updating those local paths. A personalized `AMDNR_RX9070XT_実機検証.json` was also saved into the user's normal ComfyUI `user/default/workflows/` directory, with the test input selected.

API prompt `86c30573-2e01-45fe-81ce-4353d769e72c` completed with no node errors and no cached nodes. Outputs:

| File in ComfyUI output | Size | SHA-256 |
|---|---|---|
| `AMDNR_RX9070XT_NATIVE_EXPERIMENTAL_00001_.png` | 640×360 | `4572bd6e43ea009593e9cdb5ca8c550a823cb98fa4ce289f7068e545cb3cd7bd` |
| `AMDNR_RX9070XT_NATIVE_AB_EXPERIMENTAL_00001_.png` | 1280×360 | `880ef8fd78fce29144edbb8bafa0566189ca51cd02c943f721d2b647c0b86b3b` |

ComfyUI was launched for this test on loopback port 8193 using the existing Python/core and installed custom node, with a private test user directory and only this custom node enabled. The user's regular workflow/config files were added separately for normal use. This does not test every other installed custom node together.

Browser verification also passed: the saved UI JSON opened without missing-node errors, its Run button completed successfully, and both output previews were displayed. UI prompt `4567fb3b-e768-4e60-b097-ec9646cf7bd7` reused nodes 1–6 from the preceding successful API job, so it is a UI/cache check, not an additional GPU sample. The initial frontend initialization issue cleared after reloading; no ComfyUI source or package was changed.

`AMDNRDiagnostics` describes its own read-only invocation. Its `native_gpu_smoke_test=NOT_RUN` is not a failure of a preceding render; rendering evidence is in each run's manifest.

## Private evidence and limitations

Local raw evidence is retained under ignored `local-build/enabled-validation/`, `local-build/comfy-validation/` and `runs/native/`. Job identifiers: failed conservative `job-9_58xz5s`, successful CLI `job-5ujxtls9`, successful ComfyUI API `job-o6wvtwjg`. Runtime binaries, weights and private config/log paths are excluded from source distribution.

Remaining validation: natural images, other dimensions including 1080p, long video, temporal consistency, sustained speed, peak VRAM, real GPU cancellation/recovery, and a clean installation on another PC. The color-only file path has no game depth, motion or history inputs and performs no super-resolution or frame generation. R2/R3 remain partially complete.

External runtime use is personal and non-commercial under its own license. The bridge's MIT license does not override those terms. Acquisition details and sources are in the [runtime setup guide](RUNTIME_SETUP_ja.md).
