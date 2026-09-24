"""Observe script execution while Jinja constructs imported template modules."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from collections.abc import Iterator


@dataclass
class ModuleExecution:
    used_script: bool = False


_active: ContextVar[tuple[ModuleExecution, ...]] = ContextVar('jinja_script_modules', default=())


@contextmanager
def observe_module_execution() -> Iterator[ModuleExecution]:
    record = ModuleExecution()
    token = _active.set((*_active.get(), record))
    try:
        yield record
    finally:
        _active.reset(token)


def mark_script_execution() -> None:
    # A parent macro module can capture a script from a nested import.
    for record in _active.get():
        record.used_script = True
