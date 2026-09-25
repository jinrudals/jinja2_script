"""Script instances belong to executions, never to environment globals."""

import traceback
import unittest

from jinja2 import DictLoader, Environment, StrictUndefined, UndefinedError

from jinja_script_block import ScriptBlockExtension


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.env = Environment(extensions=[ScriptBlockExtension])

    def test_execution_waits_for_render(self):
        events = []
        template = self.env.from_string(
            '{% script work %}\nevents.append("ran")\n{% endscript %}'
        )
        self.assertEqual(events, [])
        self.assertEqual(template.render(events=events), "")
        self.assertEqual(events, ["ran"])

    def test_mutable_state_is_fresh(self):
        template = self.env.from_string(
            "{% script state %}\nvalues=[]\n{% endscript %}{% set _ = state.values.append(1) %}{{ state.values|length }}"
        )
        self.assertEqual([template.render(), template.render()], ["1", "1"])

    def test_assignment_does_not_rebind_inputs(self):
        t = self.env.from_string(
            "{% script work %}\nvalue=value+1\n{% endscript %}{{ value }}:{{ work.value }}"
        )
        self.assertEqual(t.render(value=2), "2:3")

    def test_skipped_script_never_executes(self):
        t = self.env.from_string(
            '{% if enabled %}{% script work %}\nraise ValueError("unexpected")\n{% endscript %}{% endif %}'
        )
        self.assertEqual(t.render(enabled=False), "")
        with self.assertRaises(ValueError):
            t.render(enabled=True)

    def test_loop_executes_fresh_and_reads_locals(self):
        t = self.env.from_string(
            "{% for item in [4,5] %}{% script work %}\nvalues=[]\nvalues.append(item)\nindex=loop.index\n{% endscript %}{{ work.index }}:{{ work.values }};{% endfor %}{{ work is undefined }}"
        )
        self.assertEqual(t.render(), "1:[4];2:[5];True")

    def test_macro_parameters_and_local_set(self):
        t = self.env.from_string(
            "{% macro m(arg) %}{% set local=3 %}{% script work %}\nvalue=arg+local\n{% endscript %}{{ work.value }}{% endmacro %}{{ m(4) }}{{ work is undefined }}"
        )
        self.assertEqual(t.render(), "7True")

    def test_function_closes_over_current_context(self):
        t = self.env.from_string(
            "{% set local=2 %}{% script helpers %}\ndef result():\n    return supplied+local\n{% endscript %}{{ helpers.result() }}"
        )
        self.assertEqual(t.render(supplied=5), "7")
        self.assertEqual(t.render(supplied=6), "8")

    def test_no_forward_reference(self):
        e = Environment(extensions=[ScriptBlockExtension], undefined=StrictUndefined)
        t = e.from_string(
            "{{ state.value }}{% script state %}\nvalue=1\n{% endscript %}"
        )
        with self.assertRaises(UndefinedError):
            t.render()

    def test_environment_globals_unchanged(self):
        before = dict(self.env.globals)
        t = self.env.from_string("{% script state %}\nvalue=1\n{% endscript %}")
        self.assertEqual(self.env.globals, before)
        t.render()
        self.assertEqual(self.env.globals, before)

    def test_templates_do_not_overwrite_each_other(self):
        a = self.env.from_string(
            '{% script helpers %}\nvalue="A"\n{% endscript %}{{ helpers.value }}'
        )
        b = self.env.from_string(
            '{% script helpers %}\nvalue="B"\n{% endscript %}{{ helpers.value }}'
        )
        self.assertEqual([a.render(), b.render(), a.render()], ["A", "B", "A"])

    def test_caller_objects_remain_shared(self):
        t = self.env.from_string("{% script work %}\nitems.append(7)\n{% endscript %}")
        items = []
        t.render(items=items)
        self.assertEqual(items, [7])

    def test_runtime_traceback_locates_python_line(self):
        e = Environment(
            loader=DictLoader(
                {
                    "broken": 'text\n{% script work %}\nx=1\nraise ValueError("bad")\n{% endscript %}'
                }
            ),
            extensions=[ScriptBlockExtension],
        )
        t = e.get_template("broken")
        try:
            t.render()
        except ValueError as error:
            frames = traceback.extract_tb(error.__traceback__)
            self.assertTrue(
                any(
                    frame.filename == "broken" and frame.lineno == 4 for frame in frames
                ),
                frames,
            )
        else:
            self.fail("script did not raise ValueError")

    def test_runtime_failures_do_not_poison_later_render(self):
        t = self.env.from_string(
            "{% script work %}\nvalue=10/divisor\n{% endscript %}{{ work.value }}"
        )
        for _ in range(2):
            with self.assertRaises(ZeroDivisionError):
                t.render(divisor=0)
        self.assertEqual(t.render(divisor=2), "5.0")

    def test_python_only_super_binding(self):
        env = Environment(
            loader=DictLoader(
                {
                    "base": "{% block body %}base{% endblock %}",
                    "child": '{% extends "base" %}{% block body %}{% script s %}\nvalue=super()\n{% endscript %}{{ s.value }}{% endblock %}',
                }
            ),
            extensions=[ScriptBlockExtension],
        )
        self.assertEqual(env.get_template("child").render(), "base")

    def test_python_only_self_binding(self):
        t = self.env.from_string(
            "{% block body %}body{% endblock %}{% script s %}\nvalue=self['body']()\n{% endscript %}{{ s.value }}"
        )
        self.assertEqual(t.render(), "bodybody")

    def test_python_only_caller_binding(self):
        t = self.env.from_string(
            "{% macro wrap() %}{% script s %}\nvalue=caller()\n{% endscript %}{{ s.value }}{% endmacro %}{% call wrap() %}content{% endcall %}"
        )
        self.assertEqual(t.render(), "content")

    def test_python_only_macro_kwargs_and_varargs(self):
        t = self.env.from_string(
            '{% macro wrap() %}{% script s %}\nvalue=kwargs["extra"]+sum(varargs)\n{% endscript %}{{ s.value }}{% endmacro %}{{ wrap(2,3,extra=4) }}'
        )
        self.assertEqual(t.render(), "9")

    def test_python_class_super_remains_builtin(self):
        t = self.env.from_string(
            "{% script s %}\nclass Base:\n    def value(self):\n        return 4\nclass Child(Base):\n    def value(self):\n        return super().value()+1\nresult=Child().value()\n{% endscript %}{{ s.result }}"
        )
        self.assertEqual(t.render(), "5")

    def test_python_class_super_inside_inherited_block(self):
        body = "{% script s %}\nclass Base:\n    def value(self):\n        return 4\nclass Child(Base):\n    def value(self):\n        return super().value()+1\nresult=Child().value()\n{% endscript %}{{ s.result }}"
        env = Environment(
            loader=DictLoader(
                {
                    "base": "{% block body %}base{% endblock %}",
                    "child": '{% extends "base" %}{% block body %}{{ super() }}'
                    + body
                    + "{% endblock %}",
                }
            ),
            extensions=[ScriptBlockExtension],
        )
        self.assertEqual(env.get_template("child").render(), "base5")
