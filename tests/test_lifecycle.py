"""Exercise state lifetime at actual cache and scheduling boundaries."""

import asyncio
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from jinja2 import DictLoader, Environment, FileSystemBytecodeCache, Template

from jinja_script_block import ScriptBlockExtension

LIB = "{% script state %}\nvalues=[]\n{% endscript %}"
COUNT = "{% set _ = state.values.append(1) %}{{ state.values|length }}"


class LifecycleTests(unittest.TestCase):
    def test_threaded_direct_and_context_import(self):
        body = "{% script state %}\nvalue=supplied\nbarrier.wait(timeout=5)\n{% endscript %}"
        for page in [
            body + "{{ state.value }}",
            '{% from "lib" import state with context %}{{ state.value }}',
        ]:
            with self.subTest(page=page):
                barrier = threading.Barrier(2)
                env = Environment(
                    loader=DictLoader({"lib": body, "page": page}),
                    extensions=[ScriptBlockExtension],
                )
                template = env.get_template("page")
                with ThreadPoolExecutor(max_workers=2) as pool:
                    jobs = [
                        pool.submit(template.render, supplied=i, barrier=barrier)
                        for i in (1, 2)
                    ]
                    self.assertEqual(
                        [job.result(timeout=10) for job in jobs], ["1", "2"]
                    )

    def test_threaded_default_import(self):
        env = Environment(
            loader=DictLoader(
                {
                    "lib": "{% script state %}\nvalues=[]\nbarrier.wait(timeout=5)\n{% endscript %}"
                }
            ),
            extensions=[ScriptBlockExtension],
        )
        env.globals["barrier"] = threading.Barrier(2)
        template = env.from_string('{% from "lib" import state %}' + COUNT)
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(template.render) for _ in range(2)]
            self.assertEqual([job.result(timeout=10) for job in jobs], ["1", "1"])

    def test_bytecode_cache_preserves_freshness_without_compiling(self):
        sources = {
            "lib": LIB,
            "direct": LIB + COUNT,
            "from": '{% from "lib" import state %}' + COUNT,
            "import": '{% import "lib" as lib %}{% set _=lib.state.values.append(1) %}{{ lib.state.values|length }}',
            "wrapper": '{% from "lib" import state %}{% macro count() %}'
            + COUNT
            + "{% endmacro %}",
            "transitive": '{% from "wrapper" import count %}{{ count() }}',
            "included": LIB + COUNT,
            "include": '{% include "included" without context %}',
        }

        class CachedOnlyEnvironment(Environment):
            def compile(self, *args, **kwargs):
                raise AssertionError("expected a bytecode cache hit")

        with tempfile.TemporaryDirectory() as directory:
            cache = FileSystemBytecodeCache(directory)
            for cls in [Environment, CachedOnlyEnvironment]:
                env = cls(
                    loader=DictLoader(sources),
                    bytecode_cache=cache,
                    extensions=[ScriptBlockExtension],
                )
                for name in ["direct", "from", "import", "transitive", "include"]:
                    with self.subTest(environment=cls.__name__, name=name):
                        template = env.get_template(name)
                        self.assertEqual(
                            [template.render(), template.render()], ["1", "1"]
                        )

    def test_loader_auto_reload(self):
        sources = {"lib": "{% script s %}\nx=1\n{% endscript %}"}
        env = Environment(loader=DictLoader(sources), extensions=[ScriptBlockExtension])
        template = env.from_string('{% from "lib" import s %}{{ s.x }}')
        self.assertEqual(template.render(), "1")
        sources["lib"] = "{% script s %}\nx=2\n{% endscript %}"
        self.assertEqual(template.render(), "2")

    def test_closing_partial_stream_does_not_retain_state(self):
        env = Environment(extensions=[ScriptBlockExtension])
        template = env.from_string(LIB + COUNT + "tail")
        stream = template.generate()
        self.assertEqual(next(stream), "1")
        stream.close()
        self.assertEqual(template.render(), "1tail")

    def test_compile_cache_has_bounded_lifetime(self):
        from jinja_script_block.runtime import compile_script

        for i in range(160):
            compile_script(f"value={i}", f"<bounded-{i}>")
        self.assertLessEqual(compile_script.cache_info().currsize, 128)


class AsyncLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def environment(self, sources):
        return Environment(
            loader=DictLoader(sources),
            extensions=[ScriptBlockExtension],
            enable_async=True,
        )

    async def test_async_imports_and_includes(self):
        env = self.environment({"lib": LIB, "included": LIB + COUNT})
        sources = [
            '{% from "lib" import state %}' + COUNT,
            '{% import "lib" as lib %}{% set _=lib.state.values.append(1) %}{{ lib.state.values|length }}',
            '{% include "included" without context %}',
        ]
        for source in sources:
            with self.subTest(source=source):
                t = env.from_string(source)
                self.assertEqual(
                    [await t.render_async(), await t.render_async()], ["1", "1"]
                )

    async def test_interleaved_async_renders(self):
        entered = 0
        ready = asyncio.Event()

        async def synchronize():
            nonlocal entered
            entered += 1
            if entered == 2:
                ready.set()
            await asyncio.wait_for(ready.wait(), 5)
            return ""

        env = self.environment(
            {
                "lib": "{% script state %}\nvalue=supplied\n{% endscript %}{{ synchronize() }}"
            }
        )
        env.globals["synchronize"] = synchronize
        t = env.from_string(
            '{% from "lib" import state with context %}{{ state.value }}'
        )
        self.assertEqual(
            await asyncio.gather(
                t.render_async(supplied=1), t.render_async(supplied=2)
            ),
            ["1", "2"],
        )

    async def test_cancellation_resets_import_observation(self):
        started = asyncio.Event()
        release = asyncio.Event()
        ticks = []

        async def pause():
            started.set()
            await release.wait()
            return ""

        env = self.environment(
            {
                "lib": LIB + "{{ pause() }}",
                "pure": "{% set _=ticks.append(1) %}{% macro text() %}ok{% endmacro %}",
            }
        )
        env.globals.update(pause=pause, ticks=ticks)
        t = env.from_string('{% from "lib" import state %}' + COUNT)
        pure = env.from_string('{% import "pure" as p %}{{ p.text() }}')

        async def cancelled_then_continue():
            try:
                await t.render_async()
            except asyncio.CancelledError:
                pass
            self.assertEqual(
                [await pure.render_async(), await pure.render_async()], ["ok", "ok"]
            )
            self.assertEqual(ticks, [1])

        job = asyncio.create_task(cancelled_then_continue())
        await asyncio.wait_for(started.wait(), 5)
        job.cancel()
        await asyncio.wait_for(job, 5)
        release.set()
        self.assertEqual([await t.render_async(), await t.render_async()], ["1", "1"])

    async def test_async_template_globals_and_no_context(self):
        env = self.environment(
            {
                "lib": "{% script s %}\nvalue=supplied\n{% endscript %}",
                "page": '{% from "lib" import s %}{{ s.value }}',
            }
        )
        t = env.get_template("page", globals={"supplied": 7})
        self.assertEqual(await t.render_async(), "7")
        # Jinja propagates a template-global key's current context value.
        self.assertEqual(await t.render_async(supplied=9), "9")

    async def test_custom_async_module_creation(self):
        calls = []

        class CustomTemplate(Template):
            async def make_module_async(self, *args, **kwargs):
                calls.append(self.name)
                return await super().make_module_async(*args, **kwargs)

        class CustomEnvironment(Environment):
            template_class = CustomTemplate

        env = CustomEnvironment(
            loader=DictLoader({"lib": LIB}),
            extensions=[ScriptBlockExtension],
            enable_async=True,
        )
        t = env.from_string('{% from "lib" import state %}' + COUNT)
        self.assertEqual([await t.render_async(), await t.render_async()], ["1", "1"])
        self.assertEqual(calls, ["lib", "lib"])
