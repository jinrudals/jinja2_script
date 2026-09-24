# Render-Time Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the extension into render-time Python scripting with named namespaces, predictable state lifetime, and reusable helpers through standard Jinja imports.

**Architecture:** Emit ordinary Jinja assignments whose values are fresh Python modules. Keep source extraction, execution, and import lifecycle integration separate. First prove an environment-local, execution-tracking approach to import freshness; preserve normal caching for template modules whose creation executes no scripts.

**Tech Stack:** Python, Jinja 3.1.x, standard-library unittest, setuptools via pyproject.toml, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-25-render-time-scripts-design.md` (approved in conversation before this plan).

## Global Constraints

- Retain `{% script name %} ... {% endscript %}` and `{{ name.member }}`.
- Execute Python when execution reaches a script declaration, not when loading or compiling a template.
- Isolate script-created state between renders and between template executions.
- Reject duplicate script declarations within one source template during compilation.
- Allow different templates to declare the same name.
- Support explicit reuse through Jinja's `import` and `from ... import ...`, including aliases.
- Support helper-only templates and templates containing both helpers and output.
- Allow scripts to read template variables available at their execution point.
- Normal Jinja context rules apply: imports without context do not receive the caller's render variables; `with context` does.
- The snapshot is shallow. Objects supplied by the caller remain shared references: mutating an input list changes that list.
- Retain `from jinja_script_block import ScriptBlockExtension` as the entry point.
- Avoid global monkey-patching and process-wide changes to Jinja.
- Proposed support baseline: Python 3.10+ and Jinja 3.1.x.
- Async Python inside scripts is out of scope.
- Publishing a release is outside this refactor.

## Review Focus

1. `include ... without context` uses Jinja's cached template module path too; its scripts must execute on every include (Tasks 1 and 4).
2. A macro-only wrapper can capture a script imported transitively; its cached closure must not retain script state (Tasks 1 and 4).
3. Environments using overlays or custom Template classes must retain their behavior and must not share mutable script instances (Tasks 1 and 4).
4. Raw/comment regions and Python strings can contain template-looking text; extraction must not discover fake script declarations or consume Python text as Jinja (Task 2).
5. Cache hits, failed executions, async cancellation, and interleaved renders must not leave stale tracking state that changes a later render (Tasks 1, 3, and 4).

## File map and ordering

| File | Responsibility |
| --- | --- |
| `jinja_script_block/__init__.py` | Public extension and compatibility exception exports only |
| `jinja_script_block/extension.py` | Extension hooks, declaration validation, AST assignments |
| `jinja_script_block/source.py` | Raw Python extraction, dedentation, original line mapping |
| `jinja_script_block/runtime.py` | Bounded compiled-code cache and fresh module execution |
| `jinja_script_block/integration.py` | Execution observation and environment-local Template composition |
| `jinja_script_block/errors.py` | Source-aware syntax exceptions and old public exception names |
| `tests/test_source.py` | Parser, names, indentation, literal delimiter, diagnostic tests |
| `tests/test_runtime.py` | Rendering, state, context, scopes, and runtime failures |
| `tests/test_imports.py` | Imports, aliases, context, transitive exports, ordinary macros |
| `tests/test_composition.py` | Includes, inheritance, overlays, custom Template classes |
| `tests/test_lifecycle.py` | Concurrent/async execution, cancellation, caches, cleanup |
| `tests/test_basic.py` | Existing behavior, adjusted for execution timing |
| `pyproject.toml` | Build metadata, dependency bounds, explicit package discovery |
| `.github/workflows/tests.yml` | Supported Python/Jinja combinations and build checks |
| `README.md`, `examples/basic.py`, `examples/reuse.py` | Usage, reuse, migration, and executable examples |
| `docs/superpowers/experiments/import-lifecycle.md` | Feasibility findings and mechanism decision |

Execute Tasks 1–6 in order. They share runtime and integration interfaces, so native execution in this session is recommended. Use an isolated worktree at execution time through the worktree skill. Read any applicable AGENTS.md files in the resulting checkout. Keep plan/design commits in the implementation branch.

Use an isolated virtual environment during execution; commands below use its `python`. Before dependencies are installed, the existing environment can run the baseline with `python3 -m unittest discover -v`. Dependency installation requires the applicable network permissions.

## Task 1: Prove fresh imports without changing ordinary import caching

**Files:** Create `docs/superpowers/experiments/import-lifecycle.md`; prototype under `/tmp/jinja-script-import-probe/` only. No product implementation in this task.

**Interfaces to prove:**

```python
@dataclass
class ModuleExecution:
    used_script: bool = False

@contextmanager
def observe_module_execution() -> Iterator[ModuleExecution]: ...
def mark_script_execution() -> None: ...
def install_template_integration(environment: Environment) -> None: ...
```

The eventual implementation of these interfaces belongs in `integration.py`. ContextVar state contains execution records, never script namespaces. The Template mixin wraps the environment's existing Template class rather than modifying Jinja's global Template type. Bind no closures to a particular environment so overlays remain valid.

- [ ] **1. Record the baseline and isolate the probe.** Run `python3 -m unittest discover -v`; record interpreter/Jinja versions and the 12-test result. Create the temporary prototype directory. Use a tiny prototype extension that emits `nodes.Assign` and marks script execution, without building the final raw-Python parser.
- [ ] **2. Add executable unittest cases for module lifetime.** The prototype tag creates `ModuleType(name)` with `values = []`. The critical fixture is:

```python
templates = {
    "lib": "{% script state %}{% endscript %}",
    "wrapper": (
        '{% from "lib" import state %}'
        '{% macro next_value() %}'
        '{% set _ = state.values.append(1) %}{{ state.values|length }}'
        '{% endmacro %}'
    ),
    "page": '{% from "wrapper" import next_value %}{{ next_value() }}',
    "pure": '{% set _ = ticks.append(1) %}{% macro text() %}ok{% endmacro %}',
    "pure_page": '{% import "pure" as p %}{{ p.text() }}',
}
# env.globals["ticks"] = ticks before loading templates.
# Assert page.render() == page.render() == "1".
# Assert pure_page.render() == pure_page.render() == "ok" and ticks == [1].
```

Add a second import of `lib` under another alias in one render, direct and dynamic imports (`{% import target as lib %}`), and an include without context. For the include, inject a caller-owned counter through environment globals and assert it increments on both executions, instead of merely asserting identical text.
- [ ] **3. Run the probe against stock cached-module behavior.** Run `python -m unittest discover -s /tmp/jinja-script-import-probe -v`; freshness cases must fail while the pure-module cache control passes. Capture actual failures, not inferred ones.
- [ ] **4. Implement the candidate in the probe.** Use a `ContextVar` holding a tuple of observation records. `mark_script_execution()` sets every active record's `used_script` flag. A new observation uses `token = variable.set(previous + (record,))` and always resets it in `finally`.

The sync module algorithm is:

```python
def _get_default_module(self, ctx=None):
    if self.environment.is_async:
        raise RuntimeError("Module is not available in async mode.")
    if ctx is not None:
        keys = ctx.globals_keys - self.globals.keys()
        if keys:
            # Preserve Jinja's template-global propagation, not render inputs.
            return self.make_module({key: ctx.parent[key] for key in keys})
    if self._module is not None:
        return self._module
    with observe_module_execution() as observation:
        result = self.make_module()
    if not observation.used_script:
        self._module = result
    return result
```

Provide an async equivalent using `await self.make_module_async()`. Do not call the stock caching implementation and clear `_module` afterward: that could expose a cached mutable instance transiently. Marking all active records prevents a wrapper module from caching a closure over an imported script. The source template is evaluated once for each fresh import; do not render twice to classify it.

Install the mixin once with a composed class derived from `(ScriptTemplateMixin, environment.template_class)`. Guard repeated installation with `issubclass`. Exercise custom `make_module` and `make_module_async` overrides; do not claim compatibility with arbitrary custom private-method overrides if composition bypasses them.
- [ ] **5. Expand and run the probe.** Verify import context modes, both async import forms, template globals versus render inputs, overlays, custom Template behavior, repeated failed renders, and ordinary macro caching. Reload templates through a fresh environment sharing a `FileSystemBytecodeCache` and verify freshness still works. No source-parsing metadata may be required for cache hits. A macro containing a script declaration must create its script when called, even if the macro's containing module is cached.
- [ ] **6. Record the result and gate later work.** Write exact commands, results, observed constraints, Jinja internals relied on, and the selected mechanism to `docs/superpowers/experiments/import-lifecycle.md`. If the candidate fails or requires disabling all import caching, return to design review with the failing example and tradeoff. Do not silently weaken freshness, change context visibility, or add a new tag. Only proceed to Task 2 after the required behavior is proven.
- [ ] **7. Commit the evidence.** Commit only the experiment report with message `docs: verify script import lifecycle integration`. Keep probe implementation temporary; production code enters with regression tests in subsequent tasks.

## Task 2: Preserve Python source and compile-time diagnostics

**Files:** Create `source.py`, `errors.py`, `extension.py`, `tests/test_source.py`; modify `__init__.py`.

**Interfaces:**

```python
def rewrite_script_blocks(
    source: str, environment: Environment,
    name: str | None, filename: str | None,
) -> str: ...

def prepare_python(source: str, first_lineno: int) -> str: ...

class ScriptBlockExtension(Extension):
    tags = {"script"}
    def preprocess(self, source, name, filename=None) -> str: ...
    def parse(self, parser) -> nodes.Stmt: ...

class CompileError(TemplateSyntaxError): ...
class NoModuleNameDefined(TemplateSyntaxError): ...
class NoInternalJinjaAccepted(TemplateSyntaxError): ...
```

Keep old exceptions importable from `jinja_script_block`; use useful inherited messages rather than fixed misspelled messages. Additional syntax failures may use `TemplateSyntaxError` directly. Runtime execution remains temporarily at the existing timing in this task; Task 3 changes it explicitly.

- [ ] **1. Add tests for names, indentation, and source locations.** Use `unittest.TestCase` and `Environment(extensions=[ScriptBlockExtension])`:

```python
def test_duplicate_names_identify_source(self):
    source = "{% script item %}\nx = 1\n{% endscript %}\n{% script item %}\nx = 2\n{% endscript %}"
    with self.assertRaises(TemplateSyntaxError) as raised:
        self.env.compile(source, name="duplicate.jinja")
    self.assertEqual(raised.exception.name, "duplicate.jinja")
    self.assertEqual(raised.exception.lineno, 4)
    self.assertIn("item", str(raised.exception))

def test_template_delimiters_in_python_strings(self):
    template = self.env.from_string(
        '{% script text %}\nvalue = "{{ untouched }}"\n{% endscript %}'
        '{{ text.value }}'
    )
    self.assertEqual(template.render(), "{{ untouched }}")
```

Use subtests for missing name, `_private`, Python keywords, malformed end tag, empty body, comment-only body, inline body, CRLF input, blank lines, tabs, and indented multiline functions. Check duplicates across branches and macros, but permit the same name in two separately loaded templates. Add literal `{% script fake %}` inside Jinja comments and raw blocks; neither creates a declaration. Check custom block delimiters and whitespace options.
- [ ] **2. Run the new source tests.** Run `python -m unittest tests.test_source -v`; confirm failure on the new behavior before changing parsing.
- [ ] **3. Implement deterministic source extraction.** Use a local scanner driven by configured Jinja delimiters. Track text, quoted Jinja tag contents, comments, raw regions, and script bodies; do not use one regex over the entire template. Capture a script body through its configured closing tag, preserving start and end whitespace controls.

Represent each captured body inside a private encoded payload in the rewritten script tag. For example, encode `(raw_body, first_lineno)` as JSON and then as a Jinja string literal. Keep the same total newline count by padding within the rewritten tag. The payload travels with source/bytecode, not an extension-level dictionary. Reject manually supplied extra script arguments instead of exposing payload encoding as public syntax. Escape payloads correctly when custom delimiters contain quote characters; test the selected encoding.

Dedent with `textwrap.dedent`; preserve leading blank lines. Prefix the compiled Python with `"\n" * (first_lineno - 1)` so traceback lines map to the source. A literal closing script delimiter terminates the block even inside a Python string, as documented in the spec. Nested template syntax outside Python strings is invalid Python and must receive a clear compile-time error, never execute as Jinja.

The parsing core should use ordinary assignment targets:

```python
lineno = next(parser.stream).lineno
name = parser.stream.expect("name").value
# Validate isidentifier(), keyword.iskeyword(), leading underscore,
# and per-parser duplicate declaration locations before consuming payload.
# Validate decoded Python with compile(..., filename, "exec").
```

Maintain the declaration map on the parser instance with an extension-specific attribute, never on the shared extension. For the same parser encountering a repeated declaration, raise an error with the first and repeated line numbers.
- [ ] **4. Verify source behavior and old tests.** Run `python -m unittest tests.test_source tests.test_basic -v`. Verify no compile-time Python SyntaxWarning remains. Inspect a syntax error using a DictLoader template name and another using a real filename; both must point to the original line.
- [ ] **5. Commit.** Commit parser, errors, public exports, and tests with message `refactor: preserve script source and validate declarations`.

## Task 3: Execute scripts in fresh render-local namespaces

**Files:** Create `runtime.py`, `integration.py`, `tests/test_runtime.py`; modify `extension.py`, `tests/test_basic.py`.

**Interfaces:**

```python
def compile_script(source: str, filename: str) -> CodeType: ...

def execute_script(
    context: Context, name: str, source: str, filename: str,
) -> ModuleType: ...

# Source passed here is already dedented and padded to its original line.
# compile_script uses functools.lru_cache(maxsize=128).
# integration.py supplies mark_script_execution() and its observer from Task 1.
```

- [ ] **1. Add rendering tests before changing execution.**

```python
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
        '{% script state %}\nvalues = []\n{% endscript %}'
        '{% set _ = state.values.append(1) %}{{ state.values|length }}'
    )
    self.assertEqual([template.render(), template.render()], ["1", "1"])

def test_python_assignment_does_not_rebind_template_input(self):
    template = self.env.from_string(
        '{% script work %}\nvalue = value + 1\n{% endscript %}'
        '{{ value }}:{{ work.value }}'
    )
    self.assertEqual(template.render(value=2), "2:3")
```

Add skipped-conditional and per-loop execution cases, functions closing over render inputs, local `{% set %}` values, macro arguments, loop variables, `loop.index`, Python imports, functions, and classes. Use StrictUndefined to verify names are unavailable before declarations. Compare environment globals before and after compilation/rendering. Test a caller-owned list being mutated explicitly.
- [ ] **2. Run the new tests and confirm timing/state failures.** Run `python -m unittest tests.test_runtime -v` before runtime changes. Update the old NameError test to build the template first and assert NameError from `render()`.
- [ ] **3. Implement execution and AST assignment.**

```python
@lru_cache(maxsize=128)
def compile_script(source, filename):
    return compile(source, filename, "exec")

def execute_script(context, name, source, filename):
    mark_script_execution()
    module = ModuleType(name)
    module.__dict__.update(context.get_all())
    module.__dict__["__name__"] = name
    module.__dict__["__file__"] = filename
    module.__dict__["__builtins__"] = builtins.__dict__
    exec(compile_script(source, filename), module.__dict__)
    return module
```

Use an extension `_execute(context, name, source, filename)` method that delegates to this function. `parse()` returns:

```python
nodes.Assign(
    nodes.Name(name, "store"),
    self.call_method("_execute", [
        nodes.DerivedContextReference(), nodes.Const(name),
        nodes.Const(prepared_source), nodes.Const(script_filename),
    ]),
).set_lineno(lineno)
```

Validate with `compile_script` at parse time, but execute only through the runtime call. Catch only `SyntaxError` during validation and chain it into `CompileError`; leave runtime exception types intact. Use a stable descriptive filename for unnamed templates rather than giving different unnamed sources indistinguishable tracebacks. Bound any linecache/source bookkeeping if added.

Check the generated code for loop context. Jinja may omit constructing `loop` unless referenced in its AST; when a script occurs in a loop body, insert the necessary non-output `loop` reference in that scope or an equivalent minimal AST adaptation so the approved local-variable semantics hold. Do not make scripts in a nested macro accidentally bind an unrelated loop.
- [ ] **4. Run runtime and parser regressions.** Run `python -m unittest discover -v`. Add a runtime failure with traceback inspection that verifies its original exception type and script line. Ensure repeated failures do not retain observer frames by subsequently rendering an ordinary template module and verifying its normal caching behavior.
- [ ] **5. Commit.** Commit with message `feat: execute named scripts in fresh render namespaces`.

## Task 4: Integrate imports, includes, and inheritance

**Files:** Modify `integration.py`, `extension.py`; create `tests/test_imports.py`, `tests/test_composition.py`.

**Interfaces:** Install `install_template_integration(environment)` from Task 1 during extension initialization. It composes with `environment.template_class`; the runtime marks script execution using Task 3's observer. Preserve the public extension import-string identifier even though implementation moved to `extension.py`: use the existing identifier `jinja_script_block.ScriptBlockExtension` or document and test an intentional cache-breaking migration.

- [ ] **1. Add imports tests using the real extension.**

```python
loader = DictLoader({
    "lib": '{% script state %}\nvalues = []\n{% endscript %}',
    "page": (
        '{% from "lib" import state as a %}'
        '{% from "lib" import state as b %}'
        '{% set _ = a.values.append(1) %}'
        '{{ a.values|length }}:{{ b.values|length }}'
    ),
})
env = Environment(loader=loader, extensions=[ScriptBlockExtension])
page = env.get_template("page")
assert [page.render(), page.render()] == ["1:0", "1:0"]
```

Use unittest assertions in the committed suite. Cover `import ... as module`, dynamic source names, with/without context, template globals propagated through imports, transitive wrappers, and mixed-content files. A no-context helper containing `value = supplied` must raise NameError when `supplied` exists only as a caller render input; the same import with context must succeed. A pure macro library must retain its one-time initialization caching.
- [ ] **2. Add composition tests.** A parent and included file both declare `helpers`; assert output `CardPage` and unchanged parent namespace. Repeat with `without context` and a global execution counter. Include a missing template with `ignore missing` and a list of fallback names; preserve Jinja behavior. For inheritance, test overridden blocks, `super()`, scripts that never execute, and same-named local block scripts. Check ordinary alias rebinding remains ordinary Jinja behavior rather than becoming a new global duplicate rule.
- [ ] **3. Run tests against the missing import integration.** Run `python -m unittest tests.test_imports tests.test_composition -v`; verify cached script-state regressions fail before installing the Template mixin.
- [ ] **4. Port the proven lifecycle mechanism.** Move the Task 1 algorithm into `integration.py` and install it once per environment. Preserve inherited custom Template behavior and support overlays. Mark all enclosing module-creation observations, including script execution reached through includes or nested imports. A cached pure module never holds script-created mutable state from its creation. Keep Jinja's normal handling of globals, missing templates, and module exports. Use `try/finally` for observation cleanup.
- [ ] **5. Run all composition cases.** Run `python -m unittest tests.test_imports tests.test_composition tests.test_runtime -v`. Add an environment subclass with a Template subclass overriding `make_module` to record calls; verify calls still occur and unrelated environments keep stock Template classes. If the lifecycle proof needs alteration, update the experiment report with actual evidence.
- [ ] **6. Commit.** Commit with message `feat: reuse script namespaces through isolated Jinja imports`.

## Task 5: Verify concurrency, async rendering, and bytecode reuse

**Files:** Create `tests/test_lifecycle.py`; modify `integration.py`, `runtime.py`, or `extension.py` only when these regressions expose a defect.

**Interfaces:** No new public API. Exercise `Template.render`, `render_async`, `generate`, standard bytecode caching, and environment overlays.

- [ ] **1. Add deterministic concurrent-render cases.**

```python
barrier = threading.Barrier(2)
source = (
    '{% script state %}\nvalue = supplied\n'
    'barrier.wait(timeout=5)\n{% endscript %}{{ state.value }}'
)
template = env.from_string(source)
with ThreadPoolExecutor(max_workers=2) as pool:
    jobs = [pool.submit(template.render, supplied=i, barrier=barrier) for i in (1, 2)]
    self.assertEqual([job.result(timeout=10) for job in jobs], ["1", "2"])
```

Repeat using an imported helper with context. For default imports, use a shared environment-global barrier solely for synchronization, and verify each imported script's own list has length one. Do not use sleep-based race assertions.
- [ ] **2. Add cache-reload tests.**

```python
with tempfile.TemporaryDirectory() as directory:
    cache = FileSystemBytecodeCache(directory)
    def environment():
        return Environment(loader=DictLoader(sources), bytecode_cache=cache,
                           extensions=[ScriptBlockExtension])
    first = environment().get_template("page")
    self.assertEqual(first.render(), "1")
    second = environment().get_template("page")
    self.assertEqual([second.render(), second.render()], ["1", "1"])
```

Cover both import forms, the transitive wrapper fixture, a direct script template, and include without context. Confirm the second environment actually loads bytecode by wrapping its compilation path with a failure if invoked for unchanged fixtures. Test auto-reload with changed source, preserving stock loader semantics.
- [ ] **3. Add async lifecycle cases.** Use `unittest.IsolatedAsyncioTestCase`, `Environment(enable_async=True)`, and synchronous Python script bodies. Exercise `render_async`, both import forms, include without context, and concurrent `asyncio.gather` renders. Coordinate a cancellation through an awaited Jinja global immediately after a script declaration during import construction; cancel the task, then verify a later render and pure-module cache control succeed. This tests observer cleanup without allowing `await` inside Python scripts.
- [ ] **4. Run lifecycle tests and fix only demonstrated defects.** Run `python -m unittest tests.test_lifecycle -v`. Record the initial results; if they pass, do not introduce a contrived failure. If a defect appears, minimize it, retain the failing regression, and repair the responsible module. Add a partially consumed `generate()` stream that is closed, then verify another render receives fresh script state.
- [ ] **5. Run the full suite once after changes.** Run `python -m unittest discover -v` and `python -W error::SyntaxWarning -m compileall -q jinja_script_block tests`. Verify the compiled-code cache is bounded by its configured maximum; do not assert cache hit counts that merely mirror implementation.
- [ ] **6. Commit.** Commit with message `test: cover script lifecycle across concurrent renders and caches`.

## Task 6: Modernize packaging, examples, and migration documentation

**Files:** Create `pyproject.toml`, `.github/workflows/tests.yml`, `examples/reuse.py`; modify `README.md`, `examples/basic.py`, `.gitignore`; remove `setup.py`, `requirements.txt`, and `MANIFEST.in` only after their required metadata is covered.

**Interfaces:** Keep distribution `jinja-script-block`, package `jinja_script_block`, and public extension imports. Use the next minor package version `0.1.0` for this breaking pre-1.0 change, without publishing or tagging a release.

- [ ] **1. Define build metadata.**

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "jinja-script-block"
version = "0.1.0"
description = "Named Python script blocks for Jinja templates"
readme = "README.md"
requires-python = ">=3.10"
dependencies = ["Jinja2>=3.1,<3.2"]
authors = [{name = "Benjamin Jin", email = "jinrudals135@naver.com"}]

[project.urls]
Repository = "https://github.com/jinrudals/jinja2_script"

[tool.setuptools.packages.find]
include = ["jinja_script_block*"]
```

Inspect repository history for license evidence. Preserve the existing generic BSD metadata without guessing a BSD variant; if no exact terms exist, record that limitation in the handoff rather than fabricating a LICENSE. Setuptools compatibility determines whether the legacy generic declaration is expressed as `license = {text = "BSD"}`. Add no runtime dependency beyond Jinja.
- [ ] **2. Update executable examples.** Keep the original list-mutation example working under the new lifetime. Add `examples/reuse.py` using DictLoader, a `pricing` script, a function taking an `items` argument, and both import forms. A minimal reusable fixture is:

```python
env = Environment(loader=DictLoader({
    "pricing": "{% script pricing %}\ndef total(items):\n    return sum(items)\n{% endscript %}",
    "page": '{% from "pricing" import pricing %}{{ pricing.total(items) }}',
}), extensions=[ScriptBlockExtension])
print(env.get_template("page").render(items=[3, 4]))
```

Run `python -m examples.basic` and `python -m examples.reuse`; the reuse example must print `7`.
- [ ] **3. Rewrite usage and migration documentation.** Show installation, extension configuration, render-time errors, namespaced values, imports/aliases, with-context behavior, mixed-content imports, include versus import, per-template duplicate validation, state lifetime, caller-object mutation, and ordinary Python imports. State that templates execute trusted Python and that Python async syntax is not supported. Explain the deliberate import lifecycle integration and which Jinja internals it uses. Include before/after examples for environment-global reliance and exceptions moving from template loading to rendering.
- [ ] **4. Add CI and housekeeping.** Add ignores for `.venv/`, `build/`, and local tool caches while retaining existing useful ignores. Configure a matrix for supported Python versions 3.10 through the current stable version verified during execution, with Jinja 3.1.0 and the latest 3.1.x on compatible interpreters. Use official Python/Jinja sources to verify version availability, then pin CI action references appropriately. Each job installs the project and runs `python -m unittest discover -v`. One job builds both distributions and runs artifact smoke checks.
- [ ] **5. Build and test installed artifacts outside the checkout.** Install build tooling in the isolated development environment, run `python -m build`, inspect wheel and sdist contents, and install each into a separate temporary virtual environment. From a directory outside the source tree, run:

```python
from jinja2 import Environment
from jinja_script_block import ScriptBlockExtension
template = Environment(extensions=[ScriptBlockExtension]).from_string(
    "{% script demo %}\nvalue = 7\n{% endscript %}{{ demo.value }}"
)
assert template.render() == "7"
assert template.render() == "7"
```

Also run the reusable-import fixture against the installed package. Confirm tests/examples are not installed as top-level packages. Record any unavailable interpreter or network-dependent validation accurately rather than calling it passed.
- [ ] **6. Final validation and review.** Run the full suite and examples after the final changes; run `git diff --check`. Review against the spec and migration examples, especially the five Review Focus cases. Follow the chosen execution workflow's code-review and branch-finishing skills; do not merge or publish by inference. Commit with message `build: modernize package metadata and document render-time scripts`.

## Plan self-review and handoff

Coverage: Task 1 resolves import feasibility; Task 2 covers raw source and compile-time diagnostics; Task 3 covers state and context; Task 4 covers explicit reuse and template composition; Task 5 covers interleaving, caches, async behavior, and cleanup; Task 6 covers supported versions, builds, documentation, and migration. Review Focus entries each have executable regression requirements in their owning tasks.

The code snippets define implementation direction, not pre-verified results. Task 1 is an explicit technical gate: if it disproves the mechanism, revise this plan before building on it. Keep any prototype temporary and clearly distinguish its evidence from production test results.

The user must review this plan and choose execution before implementation. Recommended method: **native**, because this is a small package with tightly coupled parser, runtime, and import lifecycle changes. Implement sequentially in this session, then obtain one independent whole-branch review. Subagent-driven execution is available if the user prefers separate implementation/review gates per task.
