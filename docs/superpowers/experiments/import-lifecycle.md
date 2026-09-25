# Import lifecycle experiment

Python 3.12.3, Jinja 3.1.2. Temporary probe: `/tmp/jinja-script-import-probe`.

The prototype extension emits a normal Jinja assignment that constructs a module during rendering. Its lifecycle tests run real Jinja imports, including nested macro closures.

- Baseline: `.venv/bin/python -m unittest discover -s /tmp/jinja-script-import-probe -q`: 11 tests, 7 failures. Repeated imports returned incrementing state, two aliases shared a list, and includes without context executed once.
- Candidate: `PROBE_FIXED=1 .venv/bin/python -m unittest discover -s /tmp/jinja-script-import-probe -q`: 11 tests passed.

The candidate composes a Template mixin onto the environment's template class. When Jinja requests a default module, a ContextVar tracks whether its construction executes any script. Only modules that execute no scripts are cached. Script execution marks all enclosing observations, so a macro-only wrapper capturing an imported script is fresh too. Observations reset in finally blocks; no script module is cached even transiently.

Confirmed: ordinary macro caching, default imports, with-context imports, template-specific globals, aliases, dynamic imports, nested imports, overlays, exception cleanup, bytecode reloads, and async rendering. More extensive custom-template, cancellation, and concurrent cases remain in the production regression tasks.

The approach preserves context visibility and does not require source-scanning metadata on bytecode cache hits. Imports with context already create fresh modules. Includes without context use the same default-module path and gain the same freshness guarantee.

Integration relies on Jinja 3.1's private `_get_default_module` and `_get_default_module_async` hooks, `_module`, and `Context.globals_keys`. Custom Template `make_module` implementations remain callable through method resolution. Custom overrides of the two private cached-module hooks cannot simultaneously own that behavior; document this integration boundary. No process-wide patching or indiscriminate cache disabling is required.

## Final review refinement

The initial runtime-only classifier missed script declarations and nested imports skipped on first module construction. Final regression tests reproduced permanently cached empty exports. The production implementation therefore persists script-capability and literal-dependency metadata through a composed code generator and Template class, and checks that dependency graph before using module caches. Script-bearing dependencies prevent caching even when an earlier branch skipped their execution. Dynamic or unresolved dependencies conservatively prevent caching; known pure dependency graphs still cache. Runtime observations remain to detect indirect execution beyond static dependencies. Async rendering, bytecode reloads, and precompiled ModuleLoader paths cover this refinement.
