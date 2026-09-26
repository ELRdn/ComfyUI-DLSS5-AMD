"""Two deliberately separate backends: diagnostic CPU and experimental native NR."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import platform
from typing import Callable

import numpy as np

from .config import NativeConfig
from .contracts import FrameSpec
from .errors import ConfigurationError, ContractError, EvidenceError
from .evidence import validate_native_report
from .process import CancelCheck, run_process

# Parameters are pinned to the inspected upstream color-only profile. Scale is
# an opaque upstream model setting, NOT an output-resolution factor.
COLOR_ONLY_INI = """[DlssNrOnAmd]
Enabled=1
UseFsrInputs=0
HipDevice=-1
Inline=1
Interop=1
Scale=0.03125
LocalStructure=1
LocalTone=0
SkinStructure=-1
UseAutoMask=1
ToneChannels=0
Temporal=0
Tonemap=-1
UseDepth=0
InlineWaitMs=200
"""

@dataclass
class BackendResult:
    rgba: np.ndarray
    evidence: dict


class ReferenceBackend:
    """Diagnostic only: copies RGBA8 through files. Never claims DLSS inference."""
    name = "reference_roundtrip_NOT_DLSS"
    is_native = False

    def required_disk(self, spec: FrameSpec) -> int:
        return spec.raw_bytes * 2

    def execute(self, packed: np.ndarray, spec: FrameSpec, job: Path,
                cancel: CancelCheck | None = None) -> BackendResult:
        if cancel:
            cancel()
        input_file, output_file = job / "input.rgba", job / "output.rgba"
        packed.tofile(input_file)
        data = np.fromfile(input_file, dtype=np.uint8).reshape(packed.shape)
        data.tofile(output_file)
        if cancel:
            cancel()
        return BackendResult(data, {"level": "diagnostic_roundtrip", "neural_execution_reported": False,
                                    "independent_gpu_verification": False,
                                    "temporal_history": False, "quality_improvement_proven": False})


class NativeBackend:
    """Adapter to eikkapine's inspected raw-RGBA Windows executable contract.

    The runner argument is dependency injection for unit tests, not configurable
    from workflows or JSON. Native execution is always Windows-gated.
    """
    name = "eikkapine_native_AMD_EXPERIMENTAL"
    is_native = True

    def __init__(self, config: NativeConfig, runner: Callable = run_process):
        self.config = config
        self.runner = runner

    def required_disk(self, spec: FrameSpec) -> int:
        total_artifacts = sum(a.path.stat().st_size for a in [self.config.engine, *self.config.runtime.values()])
        # Conservative: allow per-frame copies if upstream hardlinking fails,
        # accepted captures, input/output and bounded native logs.
        return total_artifacts * (spec.frames + 1) + spec.raw_bytes * 4 + spec.frames * 64 * 1024 ** 2

    def execute(self, packed: np.ndarray, spec: FrameSpec, job: Path,
                cancel: CancelCheck | None = None) -> BackendResult:
        if platform.system() != "Windows":
            raise ConfigurationError("Native AMD NR requires Windows + D3D12. Linux CPU testing is not GPU validation.")
        if min(spec.width, spec.height) < 16 or spec.width % 2 or spec.height % 2:
            raise ContractError("Native v0.1 requires even dimensions >=16. Resize/pad explicitly before this node.")
        if spec.width > self.config.max_width or spec.height > self.config.max_height:
            raise ContractError("Native input exceeds the configured envelope; no hidden resize or tiling is applied.")
        self.config.verify()
        if cancel:
            cancel()
        engine = self.config.stage(job)
        (job / "dlssnr_on_amd.ini").write_text(COLOR_ONLY_INI, encoding="ascii")
        source, output = job / "input.rgba", job / "output.rgba"
        packed.tofile(source)
        if (job / "engine-report.json").exists() or output.exists():
            raise EvidenceError("Native workspace contains stale results.")
        argv = [str(engine), "--input", str(source), "--output", str(output),
                "--width", str(spec.width), "--height", str(spec.height),
                "--frames", str(spec.frames), "--proxy", "--out", str(job),
                "--seconds", str(self.config.timeout_seconds),
                "--worker-seconds", str(self.config.worker_seconds)]
        if self.config.fast_isolated:
            argv.append("--fast-isolated")
        env = {} if self.config.hip_device is None else {"HIP_VISIBLE_DEVICES": self.config.hip_device}
        self.runner(argv, cwd=job, log=job / "process.log",
                    timeout=self.config.timeout_seconds + 10, cancel=cancel, env_overrides=env)
        if cancel:
            cancel()
        evidence = validate_native_report(job, output, spec)
        evidence["runtime"] = self.config.private_manifest()
        data = np.fromfile(output, dtype=np.uint8).reshape(spec.frames, spec.height, spec.width, 4)
        return BackendResult(data, evidence)
