"""Explicit helper reuse must not reuse mutable script instances."""

import unittest

from jinja2 import DictLoader, Environment

from jinja_script_block import ScriptBlockExtension

LIB = "{% script state %}\nvalues=[]\n{% endscript %}"


class ImportTests(unittest.TestCase):
    def environment(self, sources):
        return Environment(
            loader=DictLoader({"lib": LIB, **sources}),
            extensions=[ScriptBlockExtension],
        )

    def test_two_aliases_are_independent(self):
        e = self.environment(
            {
                "page": '{% from "lib" import state as a %}{% from "lib" import state as b %}{% set _ = a.values.append(1) %}{{ a.values|length }}:{{ b.values|length }}'
            }
        )
        t = e.get_template("page")
        self.assertEqual([t.render(), t.render()], ["1:0", "1:0"])

    def test_module_import_and_dynamic_name(self):
        e = self.environment(
            {
                "page": "{% import target as lib %}{% set _ = lib.state.values.append(1) %}{{ lib.state.values|length }}"
            }
        )
        t = e.get_template("page")
        self.assertEqual([t.render(target="lib"), t.render(target="lib")], ["1", "1"])

    def test_import_context_rules(self):
        for form in [
            '{% from "lib" import state CONTEXT %}{{ state.value }}',
            '{% import "lib" as lib CONTEXT %}{{ lib.state.value }}',
        ]:
            for context in ["", "without context", "with context"]:
                with self.subTest(form=form, context=context):
                    e = self.environment(
                        {
                            "lib": "{% script state %}\nvalue=supplied\n{% endscript %}",
                            "page": form.replace("CONTEXT", context),
                        }
                    )
                    t = e.get_template("page")
                    if context == "with context":
                        self.assertEqual(t.render(supplied=7), "7")
                    else:
                        with self.assertRaises(NameError):
                            t.render(supplied=7)

    def test_template_specific_globals(self):
        e = self.environment(
            {
                "lib": "{% script state %}\nvalue=supplied\n{% endscript %}",
                "page": '{% from "lib" import state %}{{ state.value }}',
            }
        )
        self.assertEqual(e.get_template("page", globals={"supplied": 7}).render(), "7")

    def test_transitive_macro_does_not_capture_cached_script(self):
        e = self.environment(
            {
                "wrapper": '{% from "lib" import state %}{% macro count() %}{% set _ = state.values.append(1) %}{{ state.values|length }}{% endmacro %}',
                "page": '{% from "wrapper" import count %}{{ count() }}{{ count() }}',
            }
        )
        t = e.get_template("page")
        self.assertEqual([t.render(), t.render()], ["12", "12"])

    def test_macro_containing_script_runs_fresh(self):
        e = self.environment(
            {
                "wrapper": "{% macro count() %}{% script state %}\nvalues=[]\n{% endscript %}{% set _ = state.values.append(1) %}{{ state.values|length }}{% endmacro %}",
                "page": '{% from "wrapper" import count %}{{ count() }}{{ count() }}',
            }
        )
        t = e.get_template("page")
        self.assertEqual([t.render(), t.render()], ["11", "11"])

    def test_ordinary_macro_keeps_cache(self):
        e = self.environment(
            {
                "pure": "{% set _ = ticks.append(1) %}{% macro f() %}ok{% endmacro %}",
                "page": '{% import "pure" as p %}{{ p.f() }}',
            }
        )
        ticks = []
        e.globals["ticks"] = ticks
        t = e.get_template("page")
        self.assertEqual([t.render(), t.render()], ["ok", "ok"])
        self.assertEqual(ticks, [1])

    def test_mixed_content_is_not_emitted_by_import(self):
        e = self.environment(
            {
                "lib": "unwanted" + LIB + "content",
                "page": '{% from "lib" import state %}{{ state.values }}',
            }
        )
        self.assertEqual(e.get_template("page").render(), "[]")

    def test_jinja_alias_rebinding_is_preserved(self):
        e = self.environment(
            {
                "other": "{% script state %}\nvalues=[7]\n{% endscript %}",
                "page": '{% from "lib" import state %}{% from "other" import state %}{{ state.values }}',
            }
        )
        self.assertEqual(e.get_template("page").render(), "[7]")

    def test_import_failure_does_not_poison_cache_tracking(self):
        e = self.environment(
            {
                "bad": '{% script state %}\nraise ValueError("bad")\n{% endscript %}',
                "pure": "{% set _=ticks.append(1) %}",
                "page": '{% import "bad" as b %}',
            }
        )
        for _ in range(2):
            with self.assertRaises(ValueError):
                e.get_template("page").render()
        ticks = []
        e.globals["ticks"] = ticks
        t = e.from_string('{% import "pure" as p %}')
        t.render()
        t.render()
        self.assertEqual(ticks, [1])

    def test_skipped_script_is_reconsidered_on_later_import(self):
        for statement in [
            '{% import "lib" as lib %}',
            '{% include "lib" without context %}',
        ]:
            with self.subTest(statement=statement):
                e = self.environment(
                    {
                        "lib": "{% if flag.enabled %}{% script state %}\nevents.append(1)\n{% endscript %}{% endif %}"
                    }
                )
                flag = {"enabled": False}
                events = []
                e.globals.update(flag=flag, events=events)
                t = e.from_string(statement)
                t.render()
                flag["enabled"] = True
                t.render()
                t.render()
                self.assertEqual(events, [1, 1])

    def test_skipped_transitive_import_is_reconsidered(self):
        e = self.environment(
            {
                "wrapper": '{% if flag.enabled %}{% from "lib" import state %}{% endif %}{% macro ready() %}{{ state is defined }}{% endmacro %}',
                "page": '{% from "wrapper" import ready %}{{ ready() }}',
            }
        )
        flag = {"enabled": False}
        e.globals["flag"] = flag
        t = e.get_template("page")
        self.assertEqual(t.render(), "False")
        flag["enabled"] = True
        self.assertEqual(t.render(), "True")

    def test_pure_transitive_imports_keep_cache(self):
        e = self.environment(
            {
                "pure": "{% macro f() %}ok{% endmacro %}",
                "wrapper": '{% set _=ticks.append(1) %}{% from "pure" import f %}{% macro wrapper() %}{{ f() }}{% endmacro %}',
            }
        )
        ticks = []
        e.globals["ticks"] = ticks
        t = e.from_string('{% from "wrapper" import wrapper %}{{ wrapper() }}')
        self.assertEqual([t.render(), t.render()], ["ok", "ok"])
        self.assertEqual(ticks, [1])

    def test_skipped_missing_dependency_does_not_raise(self):
        e = self.environment(
            {
                "wrapper": '{% if false %}{% import "missing" as m %}{% endif %}{% macro f() %}ok{% endmacro %}'
            }
        )
        self.assertEqual(
            e.from_string('{% from "wrapper" import f %}{{ f() }}').render(), "ok"
        )

    def test_skipped_dynamic_import_is_reconsidered(self):
        e = self.environment(
            {
                "wrapper": "{% if flag.enabled %}{% from target import state %}{% endif %}{% macro ready() %}{{ state is defined }}{% endmacro %}"
            }
        )
        flag = {"enabled": False}
        e.globals.update(flag=flag, target="lib")
        t = e.from_string('{% from "wrapper" import ready %}{{ ready() }}')
        self.assertEqual(t.render(), "False")
        flag["enabled"] = True
        self.assertEqual(t.render(), "True")
