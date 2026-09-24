"""Parsing must preserve Python, reject ambiguous declarations, and locate errors."""

import unittest

from jinja2 import Environment, TemplateSyntaxError

from jinja_script_block import CompileError, NoModuleNameDefined, ScriptBlockExtension


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
        with self.assertRaises(NoModuleNameDefined):
            self.env.from_string("{% script %}x=1{% endscript %}")

    def test_missing_end(self):
        with self.assertRaises(TemplateSyntaxError):
            self.env.from_string("{% script a %}x=1")

    def test_syntax_error_location(self):
        source = "first\n{% script bad %}\n    x = (\n{% endscript %}"
        with self.assertRaises(CompileError) as raised:
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
