# Third-party scope and attribution

The original bridge code in this repository is supplied under the MIT license in `LICENSE`. No external native source tree, compiled runtime, model weights, NVIDIA DLL, ONNX model, game footage or proprietary asset is included.

The bridge interoperates with the documented raw-file contract of **eikkapine/DLSS5-AMD-Video**, pinned in `upstream.lock.json`. Its documentation and source informed the adapter's interface and color-only configuration. The external host's LICENSE distinguishes project-authored code from third-party material. Its documentation attributes native transport to the related MIT probe/Swapper project. Review and retain upstream notices in any build or redistribution of that code. This bridge does not grant rights to it.

The **danielblnc/DLSS-NR-on-AMD** runtime is a separate external dependency. The user-supplied `version.dll`, `nvngx_dlssnr.dll`, and `dlssnr_on_amd_weights.bin` are not covered by the bridge's MIT license. Their availability online does not establish permission to redistribute them.

The **lmxxf/dlss5-on-amd-9070xt-porting** implementation and **taowen/dlss5-onnx** are research references / future options, not bundled backends. The lmxxf ecosystem may combine MIT components with separate GPL hosts and other dependencies. No general relicensing of those components is implied.

**Blueforcer/ComfyUI-DLSS5-Enhancer** is a comparison/reference, not a bundled dependency. NVIDIA, AMD, DLSS, Radeon, ComfyUI and other names remain their respective owners' names/marks. This project is not affiliated with or endorsed by NVIDIA or AMD.

NumPy, Pillow, PyTorch, FFmpeg, Git, CMake, Windows SDK and MSVC are supplied separately under their own terms. No installed Python package or font is included in this source ZIP. See `docs/SOURCES.md` for the source URLs and scope of inspection.
