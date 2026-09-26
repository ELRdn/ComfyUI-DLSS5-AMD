"""ComfyUI entry point; importing does not load native code or start a process."""
if __package__:
    from .amd_nr.nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
else:  # Source-checkout tooling may import the hyphenated directory as __init__.
    from amd_nr.nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
