"""Persist script capability and literal dependencies in template bytecode."""

from typing import Any

from jinja2 import Environment, nodes


class ScriptCodeGeneratorMixin:
    def visit_Template(self, node: nodes.Template, frame: Any = None) -> None:
        has_scripts = any(
            attribute.identifier == "jinja_script_block.ScriptBlockExtension"
            and attribute.name == "_execute"
            for attribute in node.find_all(nodes.ExtensionAttribute)
        )
        dependencies: set[str] = set()
        dynamic = False
        for dependency in node.find_all(
            (nodes.Import, nodes.FromImport, nodes.Include, nodes.Extends)
        ):
            expression = dependency.template  # type: ignore[attr-defined]
            if isinstance(expression, nodes.Const) and isinstance(
                expression.value, str
            ):
                dependencies.add(expression.value)
            elif isinstance(expression, (nodes.List, nodes.Tuple)) and all(
                isinstance(item, nodes.Const) and isinstance(item.value, str)
                for item in expression.items
            ):
                dependencies.update(
                    item.value  # type: ignore[attr-defined]
                    for item in expression.items
                )
            else:
                dynamic = True
        # Module globals survive FileSystemBytecodeCache and ModuleLoader.
        self.writeline(  # type: ignore[attr-defined]
            f"_script_metadata = {has_scripts, dynamic, tuple(sorted(dependencies))!r}"
        )
        super().visit_Template(node, frame)  # type: ignore[misc]


def install_compiler_integration(environment: Environment) -> None:
    if not issubclass(environment.code_generator_class, ScriptCodeGeneratorMixin):
        environment.code_generator_class = type(
            "ScriptCodeGenerator",
            (ScriptCodeGeneratorMixin, environment.code_generator_class),
            {"__module__": __name__},
        )
