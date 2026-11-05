"""Template-aware errors raised while compiling script blocks."""

import warnings
from typing import Any

from jinja2 import TemplateSyntaxError

__all__ = ["ScriptBlockError", "ScriptNameError", "ScriptSyntaxError"]


class ScriptBlockError(TemplateSyntaxError):
    """Base class for every compile-time script block error."""


class ScriptNameError(ScriptBlockError):
    """A script has a missing, invalid, or duplicate namespace name."""


class ScriptSyntaxError(ScriptBlockError):
    """The Python source in a script block is invalid."""


# Names used before 0.1.0. They resolve to the new classes with a warning.
_DEPRECATED = {
    "NoModuleNameDefined": ScriptNameError,
    "NoInternalJinjaAccepted": ScriptSyntaxError,
    "CompileError": ScriptSyntaxError,
}


_USE = {
    "ScriptNameError": "raised for missing, invalid, or duplicate script names",
    "ScriptSyntaxError": "raised for invalid Python inside a script block",
}


def deprecated_error(name: str) -> Any:
    """Resolve a pre-0.1.0 exception name, warning about its replacement."""
    try:
        replacement = _DEPRECATED[name]
    except KeyError:
        raise AttributeError(name) from None
    warnings.warn(
        f"{name} is deprecated since jinja-script-block 0.1.0 and will be "
        f"removed in a future release; use jinja_script_block."
        f"{replacement.__name__} instead ({_USE[replacement.__name__]}).",
        DeprecationWarning,
        stacklevel=3,
    )
    return replacement
