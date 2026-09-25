"""Persist script capability and literal dependencies in template bytecode."""

from jinja2 import nodes


class ScriptCodeGeneratorMixin:
    def visit_Template(self, node, frame=None):
        has_scripts = any(
            attribute.identifier == "jinja_script_block.ScriptBlockExtension"
            and attribute.name == "_execute"
            for attribute in node.find_all(nodes.ExtensionAttribute)
        )
        dependencies = set()
        dynamic = False
        for dependency in node.find_all(
            (nodes.Import, nodes.FromImport, nodes.Include, nodes.Extends)
        ):
            expression = dependency.template
            if isinstance(expression, nodes.Const) and isinstance(
                expression.value, str
            ):
                dependencies.add(expression.value)
            elif isinstance(expression, (nodes.List, nodes.Tuple)) and all(
                isinstance(item, nodes.Const) and isinstance(item.value, str)
                for item in expression.items
            ):
                dependencies.update(item.value for item in expression.items)
            else:
                dynamic = True
        # Module globals survive FileSystemBytecodeCache and ModuleLoader.
        self.writeline(
            f"_script_metadata = {has_scripts, dynamic, tuple(sorted(dependencies))!r}"
        )
        super().visit_Template(node, frame)


def install_compiler_integration(environment):
    if not issubclass(environment.code_generator_class, ScriptCodeGeneratorMixin):
        environment.code_generator_class = type(
            "ScriptCodeGenerator",
            (ScriptCodeGeneratorMixin, environment.code_generator_class),
            {"__module__": __name__},
        )
