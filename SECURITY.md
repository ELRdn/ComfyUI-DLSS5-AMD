# Security and privacy

This is a local, experimental bridge, not a sandbox for untrusted code. Review the native host and every executable/runtime artifact before enabling a configuration. A matching hash detects a change relative to a pin; it does not authenticate a publisher, prove a build is reproducible, or confer a license.

Workflow JSON cannot choose an executable, DLL, shell command, or arbitrary video source path. Only trusted server configuration chooses native artifacts. Commands use argv with shell=False; local child-only HIP device selection does not alter the system environment. No routine processing sends images or logs over the network. Explicit source-fetch and runtime-setup helpers can download pinned public source or the original runtime installer. The setup helper never downloads the NVIDIA model DLL, verifies the installer and generated artifacts, uses a new private folder, and refuses to overwrite an existing configuration.

Use a local, non-shared work directory writable only by your account. This code is not a hardened multi-tenant service. Local attackers who can modify your Python, executable, configuration, runtime, or work-directory hierarchy are outside its trust boundary. A public ComfyUI server may expose queue/file operations; this project does not make that deployment safe.

Keep enough free disk and do not bypass input-size or completion checks. Native GPU crashes and out-of-memory errors may affect other work on the same device. Close important unsaved work before experimental driver/runtime testing; do not change system security settings to run this tool.

By default temporary source/output media and runtime copies are removed after each image job; manifests/logs remain. Debug retention can keep private images, DLLs and weights. Logs may contain local paths. Never upload an entire work directory as a bug report. Inspect and redact the minimum relevant text.

Publication refuses existing files and uses a complete temporary file followed by a no-replace hardlink on the destination volume. Some filesystems do not support this; failure is intentional rather than exposing partially copied media under a final filename.

Windows cancellation and native Job Object behavior have not been independently tested in this delivery. CPU/contract tests do not substitute for that gate. See ROADMAP R2.

For sharing a bug, first remove private paths, media and model/runtime binaries. The public [GitHub issue tracker](https://github.com/ELRdn/ComfyUI-DLSS5-AMD/issues) is available for sanitized reports; it is not a channel for uploading proprietary DLLs, weights, or private job folders.
