"""Privacy helpers for running third-party tools with explicit data policies.

The helpers in this package configure child-process environments. They do not
provide an operating-system network sandbox.
"""

from . import huggingface

__all__ = ["huggingface"]
