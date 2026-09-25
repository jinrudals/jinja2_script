# Refactor implementation and verification

Implemented on `refactor/render-time-scripts` from `8075dab`.

## Delivered

- Named Python script namespaces execute during rendering with fresh state.
- Source-aware compile errors and per-template duplicate-name validation.
- Explicit Jinja imports and aliases, includes, inheritance, and visible context bindings.
- Dependency-aware module caching, including skipped branches and precompiled templates.
- Isolated concurrent/async rendering, cancellation cleanup, and bounded compiled-code caching.
- Python packaging through pyproject.toml, updated examples and migration guide, and CI.

## Verification

The final suite contains 85 tests. It passed on Python 3.10.18 with Jinja 3.1.0 and on Python 3.12.3 with Jinja 3.1.6. The pre-review 69-test suite also passed on Jinja 3.1.2. Python 3.11, 3.13, and 3.14 are configured in CI but were not run locally.

Ruff lint and formatting checks, compileall with SyntaxWarnings treated as errors, both examples, and git diff whitespace checks pass. Wheel and source-distribution checks install each artifact into a separate temporary environment outside the checkout and exercise direct scripts and fresh imported state.

An independent whole-branch review found conditional module caching, line-prefix extraction, special Jinja context bindings, and unusable literal namespace names. Each production correction has a regression that failed before the fix. Extra async, bytecode-cache, and ModuleLoader cases cover the cache refinement. There are no deferred review findings.

## Decisions and boundaries

- Preserve Jinja's actual template-global override behavior: a render argument overriding a template-global key can reach a no-context import. This differs from excluding every render argument indiscriminately; changing it would break Jinja compatibility.
- Preserve supported public Template customizations, but private cached-module hook overrides remain incompatible. Applications overriding those hooks need to adapt.
- Shared caller objects and imported Python modules are not deep-isolated. The caller remains responsible for synchronization. Script bodies remain synchronous, even when the surrounding Jinja render is async.
- Preserve the historical generic BSD metadata. No exact BSD variant or license text exists in repository history; the author must resolve those terms before publishing. Setuptools emits a deprecation warning for this legacy license declaration.
- Runtime observation alone cannot detect skipped script paths. Compiled capability/dependency metadata now governs cache eligibility as well. Literal dependency inspection may load/compile referenced source early; dynamic or unresolved dependencies bypass module caching. The cost is additional initialization for uncertain pure libraries, while known pure dependency graphs retain caching.

No merge, push, package publication, or release tag was performed.
