"""Typed errors for actionable UI/CLI failures."""

class BridgeError(RuntimeError):
    """Base class. A failed native run must never fall back to another backend."""

class ContractError(BridgeError, ValueError):
    """Invalid image, setting, report, or resource contract."""

class ConfigurationError(BridgeError):
    """Missing or untrusted server-side native configuration."""

class EvidenceError(BridgeError):
    """Native completion could not be established."""

class ProcessError(BridgeError):
    """Native/FFmpeg child process failed."""

class RunCancelled(BridgeError):
    """Run cancelled; no output should be published."""

class RunTimeout(ProcessError):
    """Child exceeded its wall-time budget."""

class ResourceError(BridgeError):
    """Memory, disk, concurrency, or frame-count limit exceeded."""
