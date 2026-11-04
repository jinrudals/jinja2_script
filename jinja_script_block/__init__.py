"""Named Python script blocks for Jinja templates."""

from typing import Any

from .errors import (
    ScriptBlockError,
    ScriptNameError,
    ScriptSyntaxError,
    deprecated_error,
)
from .extension import ScriptBlockExtension

__version__ = "0.1.0"

__all__ = [
    "ScriptBlockExtension",
    "ScriptBlockError",
    "ScriptNameError",
    "ScriptSyntaxError",
    "__version__",
]


def __getattr__(name: str) -> Any:
    return deprecated_error(name)
