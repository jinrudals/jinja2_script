"""Compile reusable code and execute it in a fresh namespace."""
import builtins
from functools import lru_cache
from types import CodeType, ModuleType

from jinja2.runtime import Context

from .integration import mark_script_execution


@lru_cache(maxsize=128)
def compile_script(source: str, filename: str) -> CodeType:
    return compile(source, filename, 'exec')


def execute_script(context: Context, name: str, source: str, filename: str) -> ModuleType:
    mark_script_execution()
    module = ModuleType(name)
    module.__dict__.update(context.get_all())
    module.__dict__['__name__'] = name
    module.__dict__['__file__'] = filename
    module.__dict__['__builtins__'] = builtins.__dict__
    exec(compile_script(source, filename), module.__dict__)
    return module
