"""Template boundaries and Jinja customization remain meaningful."""

import unittest

from jinja2 import DictLoader, Environment, Template

from jinja_script_block import ScriptBlockExtension


class CompositionTests(unittest.TestCase):
    def environment(self, sources):
        return Environment(
            loader=DictLoader(sources), extensions=[ScriptBlockExtension]
        )

    def test_include_namespace_is_local(self):
        for context in ["", "without context"]:
            e = self.environment(
                {
                    "card": '{% script helpers %}\ntitle="Card"\n{% endscript %}{{ helpers.title }}',
                    "page": '{% script helpers %}\ntitle="Page"\n{% endscript %}{% include "card" CONTEXT %}{{ helpers.title }}'.replace(
                        "CONTEXT", context
                    ),
                }
            )
            with self.subTest(context=context):
                self.assertEqual(e.get_template("page").render(), "CardPage")

    def test_repeated_include_without_context_executes_each_time(self):
        e = self.environment(
            {
                "lib": "{% script s %}\nticks.append(1)\n{% endscript %}",
                "page": '{% include "lib" without context %}{% include "lib" without context %}',
            }
        )
        ticks = []
        e.globals["ticks"] = ticks
        e.get_template("page").render()
        self.assertEqual(ticks, [1, 1])

    def test_include_fallback_and_ignore_missing(self):
        e = self.environment(
            {
                "card": "{% script s %}\nx=7\n{% endscript %}{{ s.x }}",
                "page": '{% include "missing" ignore missing %}{% include ["missing", "card"] %}',
            }
        )
        self.assertEqual(e.get_template("page").render(), "7")

    def test_inheritance_override_skips_script(self):
        e = self.environment(
            {
                "base": '{% block body %}{% script s %}\nraise ValueError("not reached")\n{% endscript %}{% endblock %}',
                "child": '{% extends "base" %}{% block body %}child{% endblock %}',
            }
        )
        self.assertEqual(e.get_template("child").render(), "child")

    def test_super_keeps_local_script_namespaces(self):
        e = self.environment(
            {
                "base": '{% block body %}{% script s %}\nx="base"\n{% endscript %}{{ s.x }}{% endblock %}',
                "child": '{% extends "base" %}{% block body %}{% script s %}\nx="child"\n{% endscript %}{{ s.x }}:{{ super() }}:{{ s.x }}{% endblock %}',
            }
        )
        self.assertEqual(e.get_template("child").render(), "child:base:child")

    def test_overlay_freshness(self):
        e = self.environment(
            {
                "lib": "{% script s %}\nvalues=[]\n{% endscript %}",
                "page": '{% from "lib" import s %}{% set _=s.values.append(1) %}{{ s.values|length }}',
            }
        )
        overlay = e.overlay()
        a = e.get_template("page")
        b = overlay.get_template("page")
        self.assertEqual([a.render(), b.render(), a.render(), b.render()], ["1"] * 4)

    def test_custom_template_make_module_and_environment_isolation(self):
        calls = []

        class CustomTemplate(Template):
            def make_module(self, *args, **kwargs):
                calls.append(self.name)
                return super().make_module(*args, **kwargs)

        class CustomEnvironment(Environment):
            template_class = CustomTemplate

        e = CustomEnvironment(
            loader=DictLoader({"lib": "{% script s %}\nx=1\n{% endscript %}"}),
            extensions=[ScriptBlockExtension],
        )
        t = e.from_string('{% from "lib" import s %}{{ s.x }}')
        self.assertEqual([t.render(), t.render()], ["1", "1"])
        self.assertEqual(calls, ["lib", "lib"])
        self.assertIs(Environment().template_class, Template)
        self.assertIsInstance(e.get_template("lib"), CustomTemplate)

    def test_public_extension_import_string(self):
        e = Environment(extensions=["jinja_script_block.ScriptBlockExtension"])
        self.assertEqual(
            e.from_string("{% script s %}\nx=1\n{% endscript %}{{ s.x }}").render(), "1"
        )

    def test_include_does_not_export_script_names_to_caller(self):
        e = self.environment(
            {
                "card": "{% script helpers %}\nx=1\n{% endscript %}",
                "page": '{% include "card" %}{{ helpers is defined }}',
            }
        )
        self.assertEqual(e.get_template("page").render(), "False")

    def test_include_executes_script_with_context_only_when_allowed(self):
        e = self.environment(
            {
                "card": "{% script s %}\nv = who\n{% endscript %}{{ s.v }}",
                "with": '{% include "card" %}',
                "without": '{% include "card" without context %}',
            }
        )
        self.assertEqual(e.get_template("with").render(who="me"), "me")
        with self.assertRaises(NameError):
            e.get_template("without").render(who="me")

    def test_same_script_name_in_parent_and_child_blocks(self):
        e = self.environment(
            {
                "base": '{% block a %}{% script s %}\nv="base"\n{% endscript %}{{ s.v }}{% endblock %}{% block b %}{% script s2 %}\nv="b"\n{% endscript %}{{ s2.v }}{% endblock %}',
                "child": '{% extends "base" %}{% block a %}{% script s %}\nv="child"\n{% endscript %}{{ s.v }}{% endblock %}',
            }
        )
        self.assertEqual(e.get_template("child").render(), "childb")

    def test_script_in_child_outside_blocks_runs_before_parent_blocks(self):
        events = []
        e = self.environment(
            {
                "base": "{% block a %}x{% endblock %}",
                "child": '{% extends "base" %}{% script s %}\nevents.append("child")\n{% endscript %}',
            }
        )
        e.get_template("child").render(events=events)
        self.assertEqual(events, ["child"])

    def test_duplicate_names_are_validated_per_source_template_across_extends(self):
        e = self.environment(
            {
                "base": "{% script s %}x=1{% endscript %}{% block a %}{% endblock %}",
                "child": '{% extends "base" %}{% block a %}{% script s %}x=2{% endscript %}{% endblock %}',
            }
        )
        self.assertEqual(e.get_template("child").render(), "")
