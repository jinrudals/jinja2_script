"""Jinja parsing and namespace binding for Python script blocks."""

import hashlib
import keyword

from jinja2 import TemplateSyntaxError, nodes
from jinja2.ext import Extension

from .errors import CompileError
from .integration import install_template_integration
from .runtime import compile_script, execute_script
from .source import decode_script, prepare_python, rewrite_script_blocks


class ScriptBlockExtension(Extension):
    """Define an explicitly named Python namespace inside a template."""

    tags = {"script"}

    def __init__(self, environment):
        super().__init__(environment)
        install_template_integration(environment)

    def preprocess(self, source, name, filename=None):
        return rewrite_script_blocks(source, self.environment, name, filename)

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        name = parser.stream.expect("name").value
        if not name.isidentifier() or keyword.iskeyword(name) or name.startswith("_"):
            raise TemplateSyntaxError(
                "Invalid public script namespace: " + name,
                lineno,
                parser.name,
                parser.filename,
            )
        declarations = getattr(parser, "_script_block_declarations", None)
        if declarations is None:
            declarations = parser._script_block_declarations = {}
        if name in declarations:
            raise TemplateSyntaxError(
                f"Duplicate script {name!r}; first declared at line {declarations[name]}",
                lineno,
                parser.name,
                parser.filename,
            )
        declarations[name] = lineno
        payload = parser.stream.expect("string").value
        body, first_lineno = decode_script(payload)
        source = prepare_python(body, first_lineno)
        filename = (
            parser.filename
            or parser.name
            or f"<script:{hashlib.sha256(source.encode()).hexdigest()[:12]}>"
        )
        try:
            compile_script(source, filename)
        except SyntaxError as error:
            raise CompileError(
                error.msg, error.lineno or lineno, parser.name, parser.filename
            ) from error
        assignment = nodes.Assign(
            nodes.Name(name, "store"),
            self.call_method(
                "_execute",
                [
                    nodes.DerivedContextReference(),
                    nodes.Const(name),
                    nodes.Const(source),
                    nodes.Const(filename),
                ],
            ),
        ).set_lineno(lineno)
        # Make Jinja construct loop metadata even when only Python uses it.
        return [
            nodes.ExprStmt(nodes.Name("loop", "load")).set_lineno(lineno),
            assignment,
        ]

    def _execute(self, context, name, source, filename):
        return execute_script(context, name, source, filename)


# Preserve the original extension identifier in generated templates.
ScriptBlockExtension.identifier = "jinja_script_block.ScriptBlockExtension"
