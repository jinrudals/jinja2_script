"""Parsing must preserve Python, reject ambiguous declarations, and locate errors."""

import unittest

from jinja2 import Environment, TemplateSyntaxError

import jinja_script_block
from jinja_script_block import (
    ScriptBlockError,
    ScriptBlockExtension,
    ScriptNameError,
    ScriptSyntaxError,
)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.env = Environment(extensions=[ScriptBlockExtension])

    def test_duplicate_names_identify_source(self):
        source = "{% script item %}\nx = 1\n{% endscript %}\n{% script item %}\nx = 2\n{% endscript %}"
        with self.assertRaises(TemplateSyntaxError) as raised:
            self.env.compile(source, name="duplicate.jinja")
        self.assertEqual(raised.exception.name, "duplicate.jinja")
        self.assertEqual(raised.exception.lineno, 4)
        self.assertIn("item", str(raised.exception))
        self.assertIn("1", str(raised.exception))

    def test_duplicate_across_scopes(self):
        for source in [
            "{% if true %}{% script item %}x=1{% endscript %}{% else %}{% script item %}x=2{% endscript %}{% endif %}",
            "{% macro f() %}{% script item %}x=1{% endscript %}{% endmacro %}{% script item %}x=2{% endscript %}",
        ]:
            with self.subTest(source=source), self.assertRaises(TemplateSyntaxError):
                self.env.from_string(source)

    def test_delimiters_inside_python_strings(self):
        for value in [
            "{{ untouched }}",
            "{% if broken",
            "{# comment #}",
            '"quotes"',
            "{% script fake %}",
        ]:
            with self.subTest(value=value):
                template = self.env.from_string(
                    "{% script text %}\nvalue = "
                    + repr(value)
                    + "\n{% endscript %}{{ text.value }}"
                )
                self.assertEqual(template.render(), value)

    def test_empty_and_comment_only(self):
        for body in ["", "   ", "\n# comment\n", "\n\n"]:
            with self.subTest(body=body):
                self.assertEqual(
                    self.env.from_string(
                        "{% script empty %}" + body + "{% endscript %}ok"
                    ).render(),
                    "ok",
                )

    def test_indentation(self):
        for body in [
            "value=7",
            "\n    value = 7\n",
            "\r\n\tvalue = 7\r\n",
            "\n\n  # first\n  def f():\n      return 7\n  value = f()\n",
        ]:
            with self.subTest(body=body):
                self.assertEqual(
                    self.env.from_string(
                        "{% script s %}" + body + "{% endscript %}{{ s.value }}"
                    ).render(),
                    "7",
                )

    def test_invalid_names(self):
        for name in ["_private", "class", "a.b", "42", "a b"]:
            with self.subTest(name=name), self.assertRaises(TemplateSyntaxError):
                self.env.from_string("{% script " + name + " %}x=1{% endscript %}")

    def test_missing_name(self):
        with self.assertRaises(ScriptNameError):
            self.env.from_string("{% script %}x=1{% endscript %}")

    def test_deprecated_error_names(self):
        for old, new in [
            ("NoModuleNameDefined", ScriptNameError),
            ("NoInternalJinjaAccepted", ScriptSyntaxError),
            ("CompileError", ScriptSyntaxError),
        ]:
            with self.subTest(old=old), self.assertWarns(DeprecationWarning):
                self.assertIs(getattr(jinja_script_block, old), new)
        with self.assertRaises(AttributeError):
            jinja_script_block.Missing

    def test_error_hierarchy(self):
        for error in [ScriptNameError, ScriptSyntaxError]:
            self.assertTrue(issubclass(error, ScriptBlockError))
            self.assertTrue(issubclass(error, TemplateSyntaxError))
        with self.assertRaises(ScriptNameError):
            self.env.from_string("{% script _x %}{% endscript %}")

    def test_missing_end(self):
        with self.assertRaises(TemplateSyntaxError):
            self.env.from_string("{% script a %}x=1")

    def test_syntax_error_location(self):
        source = "first\n{% script bad %}\n    x = (\n{% endscript %}"
        with self.assertRaises(ScriptSyntaxError) as raised:
            self.env.compile(
                source, name="broken.jinja", filename="/templates/broken.jinja"
            )
        self.assertEqual(raised.exception.lineno, 3)
        self.assertEqual(raised.exception.name, "broken.jinja")
        self.assertEqual(raised.exception.filename, "/templates/broken.jinja")
        self.assertIsInstance(raised.exception.__cause__, SyntaxError)

    def test_raw_comments_and_jinja_strings(self):
        source = '{# {% script fake %} #}{% raw %}{% script fake %}{% endraw %}{{ "{% script fake %}" }}'
        self.assertEqual(
            self.env.from_string(source).render(), "{% script fake %}{% script fake %}"
        )

    def test_nested_jinja_rejected(self):
        with self.assertRaises(TemplateSyntaxError):
            self.env.from_string(
                "{% script bad %}{% if true %}x=1{% endif %}{% endscript %}"
            )

    def test_names_are_per_template(self):
        self.env.from_string("{% script s %}x=1{% endscript %}")
        self.assertEqual(
            self.env.from_string("{% script s %}x=2{% endscript %}{{ s.x }}").render(),
            "2",
        )

    def test_custom_delimiters(self):
        for begin, end in [("[%", "%]"), ("<'", "'>")]:
            with self.subTest(begin=begin):
                env = Environment(
                    extensions=[ScriptBlockExtension],
                    block_start_string=begin,
                    block_end_string=end,
                )
                source = (
                    begin
                    + " script s "
                    + end
                    + "\nvalue = 7\n"
                    + begin
                    + " endscript "
                    + end
                    + "{{ s.value }}"
                )
                self.assertEqual(env.from_string(source).render(), "7")

    def test_whitespace_control(self):
        for options in [{}, {"trim_blocks": True, "lstrip_blocks": True}]:
            env = Environment(extensions=[ScriptBlockExtension], **options)
            self.assertEqual(
                env.from_string(
                    "before \n {%- script s -%}\n x=1\n {%- endscript -%}\n after"
                ).render(),
                "beforeafter",
            )

    def test_error_after_script_retains_line(self):
        with self.assertRaises(TemplateSyntaxError) as raised:
            self.env.from_string(
                "{% script a %}\nx=1\n{% endscript %}\n{% nonexistent %}"
            )
        self.assertEqual(raised.exception.lineno, 4)

    def test_line_comments_do_not_declare_scripts(self):
        env = Environment(extensions=[ScriptBlockExtension], line_comment_prefix="##")
        for source, expected in [
            ("## {% script fake %}\nOK", "\nOK"),
            ("text ## {% script fake %}\nOK", "text\nOK"),
        ]:
            with self.subTest(source=source):
                self.assertEqual(env.from_string(source).render(), expected)

    def test_line_statements_preserve_quoted_script_text(self):
        env = Environment(extensions=[ScriptBlockExtension], line_statement_prefix="#")
        for source in [
            '# set x = "{% script fake %}"\n{{ x }}',
            '# set x = (\n "{% script fake %}"\n)\n{{ x }}',
        ]:
            with self.subTest(source=source):
                self.assertEqual(env.from_string(source).render(), "{% script fake %}")

    def test_jinja_literal_namespace_names_are_rejected(self):
        for name in ["true", "false", "none"]:
            with self.subTest(name=name), self.assertRaises(TemplateSyntaxError):
                self.env.from_string("{% script " + name + " %}\nx=1\n{% endscript %}")


class ErrorMessageTests(unittest.TestCase):
    def setUp(self):
        self.env = Environment(extensions=[ScriptBlockExtension])

    def compile_error(self, source, **kwargs):
        with self.assertRaises(ScriptBlockError) as raised:
            self.env.compile(source, name="page.html", **kwargs)
        return raised.exception

    def test_invalid_name_message_gives_reason_and_location(self):
        for name, reason in [
            ("_x", "underscore"),
            ("class", "reserved"),
            ("a.b", "identifier"),
            ("42", "identifier"),
        ]:
            with self.subTest(name=name):
                error = self.compile_error(
                    "a\n{% script " + name + " %}x=1{% endscript %}"
                )
                self.assertIsInstance(error, ScriptNameError)
                self.assertIn(repr(name), error.message)
                self.assertIn(reason, error.message)
                self.assertEqual((error.lineno, error.name), (2, "page.html"))

    def test_extra_name_tokens(self):
        error = self.compile_error("{% script a b %}x=1{% endscript %}")
        self.assertIsInstance(error, ScriptNameError)
        self.assertIn("a b", error.message)

    def test_duplicate_message_names_template_and_both_lines(self):
        error = self.compile_error(
            "{% script x %}1{% endscript %}\n\n{% script x %}2{% endscript %}"
        )
        self.assertIsInstance(error, ScriptNameError)
        self.assertEqual(error.lineno, 3)
        for text in ["'x'", "page.html", "first declared at line 1", "line 3"]:
            self.assertIn(text, error.message)

    def test_python_syntax_error_uses_template_line_and_script_name(self):
        error = self.compile_error(
            "a\nb\n{% script bad %}\n    x = 1\n    if x:\n    y = 2\n{% endscript %}"
        )
        self.assertIsInstance(error, ScriptSyntaxError)
        self.assertEqual((error.lineno, error.name), (6, "page.html"))
        self.assertIn("'bad'", error.message)
        self.assertIn("template line 6", error.message)

    def test_unterminated_script(self):
        error = self.compile_error("a\n{% script x %}\nx = 1")
        self.assertIs(type(error), ScriptBlockError)
        self.assertEqual((error.lineno, error.name), (2, "page.html"))
        self.assertIn("'x'", error.message)
        self.assertIn("endscript", error.message)

    def test_stray_endscript(self):
        error = self.compile_error("a\n\n{% endscript %}")
        self.assertIs(type(error), ScriptBlockError)
        self.assertEqual(error.lineno, 3)
        self.assertIn("endscript", error.message)

    def test_endscript_text_in_raw_is_not_stray(self):
        source = "{% raw %}{% endscript %}{% endraw %}"
        self.assertEqual(self.env.from_string(source).render(), "{% endscript %}")

    def test_deprecated_messages_name_replacement(self):
        for old, new in [
            ("NoModuleNameDefined", "ScriptNameError"),
            ("NoInternalJinjaAccepted", "ScriptSyntaxError"),
            ("CompileError", "ScriptSyntaxError"),
        ]:
            with self.subTest(old=old), self.assertWarns(DeprecationWarning) as caught:
                getattr(jinja_script_block, old)
            message = str(caught.warning)
            self.assertIn(old, message)
            self.assertIn("jinja_script_block." + new, message)
            self.assertIn("0.1.0", message)
