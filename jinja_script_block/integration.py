"""Observe script execution while Jinja constructs imported template modules."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from jinja2 import TemplateError

from .compiler import install_compiler_integration


@dataclass
class ModuleExecution:
    used_script: bool = False


_active: ContextVar[tuple[ModuleExecution, ...]] = ContextVar(
    "jinja_script_modules", default=()
)


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


class ScriptTemplateMixin:
    """Cache modules only when their dependency graph and execution are script-free.

    Jinja 3.1's two private default-module hooks also serve includes without
    context. Keep their globals semantics, but never publish a script-bearing
    module in the cache, even briefly during concurrent rendering.
    """

    @classmethod
    def _from_namespace(cls, environment, namespace, globals):
        template = super()._from_namespace(environment, namespace, globals)
        # Unknown externally compiled templates must not be assumed pure.
        template._script_metadata = namespace.get("_script_metadata", (True, True, ()))
        return template

    def _script_sensitive(self, seen=None):
        has_scripts, dynamic, dependencies = self._script_metadata
        if has_scripts or dynamic:
            return True
        if seen is None:
            seen = set()
        key = self.name if self.name is not None else id(self)
        if key in seen:
            return False
        seen.add(key)
        for name in dependencies:
            if self.environment.loader is None:
                return True
            try:
                dependency = self.environment.get_template(name, self.name)
            except (TemplateError, OSError):
                # A skipped dependency may be missing or invalid. Preserve
                # its ordinary error timing, but do not cache uncertain state.
                return True
            if not isinstance(
                dependency, ScriptTemplateMixin
            ) or dependency._script_sensitive(seen):
                return True
        return False

    def _get_default_module(self, ctx=None):
        if self.environment.is_async:
            raise RuntimeError("Module is not available in async mode.")
        if ctx is not None:
            keys = ctx.globals_keys - self.globals.keys()
            if keys:
                return self.make_module({key: ctx.parent[key] for key in keys})
        if self._script_sensitive():
            mark_script_execution()
            return self.make_module()
        if self._module is not None:
            return self._module
        with observe_module_execution() as observation:
            result = self.make_module()
        if not observation.used_script:
            self._module = result
        return result

    async def _get_default_module_async(self, ctx=None):
        if ctx is not None:
            keys = ctx.globals_keys - self.globals.keys()
            if keys:
                return await self.make_module_async(
                    {key: ctx.parent[key] for key in keys}
                )
        if self._script_sensitive():
            mark_script_execution()
            return await self.make_module_async()
        if self._module is not None:
            return self._module
        with observe_module_execution() as observation:
            result = await self.make_module_async()
        if not observation.used_script:
            self._module = result
        return result


def install_template_integration(environment) -> None:
    """Compose per environment, preserving custom public Template methods."""
    install_compiler_integration(environment)
    if not issubclass(environment.template_class, ScriptTemplateMixin):
        environment.template_class = type(
            "ScriptTemplate",
            (ScriptTemplateMixin, environment.template_class),
            {"__module__": __name__},
        )
