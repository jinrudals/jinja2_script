"""Capture raw Python before Jinja's lexer interprets its delimiters."""

import base64
import json
import re
import symtable
import textwrap

from jinja2 import TemplateSyntaxError
from jinja2.lexer import compile_rules

from .errors import NoModuleNameDefined


def _tag_end(source: str, start: int, delimiter: str) -> int:
    """Locate a Jinja delimiter outside quoted expression strings."""
    quote = None
    brackets = []
    i = start
    while i < len(source):
        if quote:
            if source[i] == "\\":
                i += 2
                continue
            if source[i] == quote:
                quote = None
        elif not brackets and source.startswith(delimiter, i):
            return i
        elif source[i] in "\"'":
            quote = source[i]
        elif delimiter == "\n" and source[i] in "([{":
            brackets.append(source[i])
        elif delimiter == "\n" and source[i] in ")]}":
            if brackets:
                brackets.pop()
        i += 1
    return -1


def prepare_python(source: str, first_lineno: int) -> str:
    """Dedent without losing the template's original line numbers."""
    return "\n" * (first_lineno - 1) + textwrap.dedent(source)


def rewrite_script_blocks(source, environment, name, filename=None):
    # Normalize just as Jinja's lexer does, before counting source lines.
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    block_start, block_end = (
        environment.block_start_string,
        environment.block_end_string,
    )
    root = re.compile(
        "|".join(
            f"(?P<{kind}>{pattern})" for kind, pattern in compile_rules(environment)
        ),
        re.MULTILINE,
    )
    ends = {
        "block_begin": block_end,
        "variable_begin": environment.variable_end_string,
        "comment_begin": environment.comment_end_string,
    }
    close_script = re.compile(
        re.escape(block_start) + r"[+-]?\s*endscript\s*[+-]?" + re.escape(block_end)
    )
    close_raw = re.compile(
        re.escape(block_start) + r"[+-]?\s*endraw\s*[+-]?" + re.escape(block_end)
    )
    chunks = []
    cursor = 0
    while cursor < len(source):
        match = root.search(source, cursor)
        if match is None:
            chunks.append(source[cursor:])
            break
        pos, kind = match.start(), match.lastgroup
        chunks.append(source[cursor:pos])
        content_start = match.end()
        if kind in ("linecomment_begin", "linestatement_begin"):
            end = (
                source.find("\n", content_start)
                if kind == "linecomment_begin"
                else _tag_end(source, content_start, "\n")
            )
            after = end + 1 if end >= 0 else len(source)
            chunks.append(source[pos:after])
            cursor = after
            continue
        end = (
            source.find(ends[kind], content_start)
            if kind == "comment_begin"
            else _tag_end(source, content_start, ends[kind])
        )
        if end < 0:
            chunks.append(source[pos:])  # Let Jinja report malformed ordinary tags.
            break
        after = end + len(ends[kind])
        header = source[content_start:end].strip()
        header = (
            header.removeprefix("-")
            .removeprefix("+")
            .removesuffix("-")
            .removesuffix("+")
            .strip()
        )
        words = header.split()
        if kind == "block_begin" and words == ["raw"]:
            close = close_raw.search(source, after)
            after = close.end() if close else len(source)
        elif kind == "block_begin" and words and words[0] == "script":
            lineno = source.count("\n", 0, pos) + 1
            if len(words) == 1:
                raise NoModuleNameDefined(
                    "A script block requires a namespace name", lineno, name, filename
                )
            if len(words) != 2:
                raise TemplateSyntaxError(
                    "Expected one script namespace name", lineno, name, filename
                )
            close = close_script.search(source, after)
            if close is None:
                raise TemplateSyntaxError(
                    "Missing endscript tag", lineno, name, filename
                )
            first_lineno = source.count("\n", 0, after) + 1
            body = source[after : close.start()]
            payload = base64.b64encode(
                json.dumps([body, first_lineno]).encode()
            ).decode()
            opening_flag = source[content_start : content_start + 1]
            opening_flag = opening_flag if opening_flag in ("-", "+") else ""
            closing_content = source[
                close.start() + len(block_start) : close.end() - len(block_end)
            ]
            closing_flag = (
                closing_content[-1:] if closing_content[-1:] in ("-", "+") else ""
            )
            # All original newlines remain inside this replacement tag.
            padding = "\n" * source.count("\n", pos, close.end())
            chunks.append(
                f'{block_start}{opening_flag} script {words[1]} "{payload}"{padding} {closing_flag}{block_end}'
            )
            cursor = close.end()
            continue
        chunks.append(source[pos:after])
        cursor = after
    return "".join(chunks)


def decode_script(payload: str) -> tuple[str, int]:
    body, lineno = json.loads(base64.b64decode(payload).decode())
    return body, lineno


def referenced_context_names(source: str, filename: str) -> tuple[str, ...]:
    """Find Jinja's compiler-created names used as Python globals.

    Method parameters such as self are local Python names. A method with a
    __class__ closure needs Python's builtin super, not Jinja's block helper.
    """
    special = {"loop", "self", "super", "caller", "kwargs", "varargs"}
    found = set()

    def visit(table):
        symbols = {symbol.get_name(): symbol for symbol in table.get_symbols()}
        class_cell = symbols.get("__class__")
        for name in special & symbols.keys():
            symbol = symbols[name]
            if symbol.is_referenced() and symbol.is_global():
                if name != "super" or not (class_cell and class_cell.is_free()):
                    found.add(name)
        for child in table.get_children():
            visit(child)

    visit(symtable.symtable(source, filename, "exec"))
    return tuple(sorted(found))
