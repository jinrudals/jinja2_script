"""Source-aware errors, including the original public exception names."""
from jinja2 import TemplateSyntaxError


class NoModuleNameDefined(TemplateSyntaxError):
    """A script declaration is missing its namespace name."""


class NoInternalJinjaAccepted(TemplateSyntaxError):
    """Compatibility name for invalid template syntax inside Python."""


class CompileError(NoInternalJinjaAccepted):
    """The Python source in a script block is invalid."""
