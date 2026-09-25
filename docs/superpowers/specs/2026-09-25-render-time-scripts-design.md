# Render-time scripts and reusable template helpers

Status: approved by the user; implemented on `refactor/render-time-scripts`. See the implementation report for verification and review refinements.

## Intent and agreed direction

Refactor the existing Jinja extension into a maintainable scripting extension for engineers. Preserve explicit script namespaces while adopting ERB-like execution during rendering. Multiple contributors must be able to organize helpers without making all Python names globally unique.

Agreed requirements:

- Retain `{% script name %} ... {% endscript %}` and `{{ name.member }}`.
- Execute Python when execution reaches a script declaration, not when loading or compiling a template.
- Isolate script-created state between renders and between template executions.
- Reject duplicate script declarations within one source template during compilation.
- Allow different templates to declare the same name.
- Support explicit reuse through Jinja's `import` and `from ... import ...`, including aliases.
- Support helper-only templates and templates containing both helpers and output.
- Allow scripts to read template variables available at their execution point.

Success means predictable state lifetime, useful diagnostics, explicit helper reuse, and a documented package whose behavior is covered by tests.

## Existing project and baseline

The implementation currently parses Python through Jinja statement nodes, normalizes indentation using regular expressions, executes Python during parsing, and writes modules into `environment.globals`. This creates shared mutable state and cross-template name collisions. Broad exception handlers obscure source errors.

The existing 12 unittest tests passed under Python 3.12.3 and Jinja 3.1.2 during exploration. Python also reported an invalid escape-sequence warning. No implementation changes have been made.

## Public behavior

### Declarations and execution

```jinja2
{% script pricing %}
def total(items):
    return sum(item.price for item in items)
{% endscript %}
{{ pricing.total(items) }}
```

A declaration binds a fresh Python module namespace to its name in the current Jinja scope. It produces no template output. Names become available after execution of the declaration; there is no forward availability.

A skipped conditional does not execute its scripts. A declaration inside a loop executes afresh on every iteration. Repeated execution of one declaration is not a duplicate declaration. Two declarations with the same name in one source file are duplicates even if they occur in different branches, blocks, or macros.

Bindings follow Jinja's lexical scoping rules. A declaration in a loop, macro, or inheritance block does not gain special visibility outside that scope. Script names must be valid Python identifiers and must not start with an underscore, so every accepted public name is compatible with Jinja's import restrictions.

Script blocks contain Python, not nested Jinja expressions or statements. Preserve blank lines and relative indentation using standard dedentation, including empty blocks and comment-only blocks. Literal Jinja delimiter sequences inside Python strings require deliberate parser handling and regression coverage; they must not be silently interpreted as nested template code. A literal endscript delimiter remains the template block terminator and must be documented as such.

### Context and state

Scripts receive a snapshot of visible template bindings, including render inputs and local variables at the declaration. Python assignments remain in the script namespace and do not rebind the surrounding Jinja variables. Names defined by Python take precedence inside that namespace.

The snapshot is shallow. Objects supplied by the caller remain shared references: mutating an input list changes that list. Python imports retain normal Python module caching. Fresh script state does not promise deep isolation of caller objects, imported libraries, files, or external services.

No script instance is stored in environment globals, an extension-wide mutable namespace, or a cached imported template module. Immutable compiled code may be cached with bounded lifetime. Concurrent renders must never exchange extension-owned script instances.

### Explicit reuse

```jinja2
{% from "scripts/pricing.jinja" import pricing %}
{{ pricing.total(items) }}

{% from "scripts/retail.jinja" import pricing as retail %}
{% from "scripts/wholesale.jinja" import pricing as wholesale %}
{{ retail.total(items) }} / {{ wholesale.total(items) }}

{% import "scripts/pricing.jinja" as helpers %}
{{ helpers.pricing.total(items) }}
```

Executed top-level declarations are exported using Jinja's normal template export mechanism. Scripts confined to local scopes are not automatically exported. Imports execute the source template to construct its exports; its rendered text is not emitted into the caller. Other top-level template code can still execute and raise errors, so helper-only templates are the recommended reusable library format.

Each import execution creates fresh script state. Two independent imports of the same source create independent instances, even during the same render. Subsequent uses of a single bound alias share that imported instance.

Normal Jinja context rules apply: imports without context do not receive the caller's render variables; `with context` does. Reusable helpers should normally accept their inputs as function arguments.

Duplicate-declaration validation covers script declarations, not every Jinja variable assignment or import alias. Ordinary Jinja rebinding retains its existing behavior; users choose distinct aliases when importing conflicting names.

### Includes and inheritance

`include` renders another template and does not export its scripts into its caller. An included template declaring a script with the same name as an incoming variable binds a new local namespace rather than mutating the incoming object. Each include execution gets fresh script instances. Explicitly passed objects retain the shallow-reference semantics described above.

`extends` follows Jinja's execution order and scope rules. Duplicate validation is per source template, not across an inheritance chain. A script in an overridden block does not run unless that block executes, for example through `super()`. Block-local script bindings must not overwrite bindings in another inheritance block scope. This design does not promise a separate globally addressable namespace for each file in an inheritance chain: reusable helpers should be imported explicitly where needed.

## Architecture

Keep the implementation small, with these responsibilities separated:

1. Parsing and validation: capture script source, track declaration names per source template, dedent Python, validate syntax, and preserve source locations.
2. Execution: build fresh namespaces, provide visible bindings, execute compiled Python, and preserve useful exception information.
3. Jinja integration: emit script assignments and exports in the proper scope and control import instantiation without leaking mutable state.

Retain `from jinja_script_block import ScriptBlockExtension` as the entry point. Split modules only where they provide these clear boundaries. Preserve existing exception names as compatibility exports where practical, while making syntax diagnostics compatible with Jinja's template-error reporting.

Prefer ordinary Jinja nodes and extension hooks. Avoid global monkey-patching and process-wide changes to Jinja. Environment-specific integration may be required for import execution; if so, it must compose with environment configuration and be explicitly documented.

## Import caching feasibility gate

Read-only inspection of installed Jinja 3.1.2 confirms that ordinary imports call `_get_default_module`, while imports with context call `make_module` using caller bindings. Ordinary cached module imports would violate the agreed state lifetime. Simply treating every import as `with context` would also violate the agreed context rules.

The first implementation-plan task must verify an environment-local integration that creates fresh imported modules while preserving the selected context behavior. Cover both import forms, nested and dynamic imports, ordinary macros, and a second render of a previously loaded template. Include templates restored from a bytecode cache so correctness does not rely only on parsing-time metadata.

Prefer targeting imports that can expose scripts. If freshness requires all imports in an extension-enabled environment to instantiate afresh, quantify and document the effect on ordinary imports and bring that tradeoff back for design review before adopting it. If standard imports cannot satisfy these requirements without broader behavior changes, stop and revise the design with the user; do not silently introduce a new tag or share instances.

The implementation plan must resolve this mechanism before treating the runtime architecture as proven. This document defines the required behavior, not a claim that stock extension hooks already provide it.

## Errors and diagnostics

- Missing or invalid script names, duplicate declarations, malformed block structure, and invalid Python fail during template compilation.
- Diagnostics identify the template and original source line; duplicates identify the repeated name and both declaration locations where feasible.
- Script runtime failures occur during rendering or import execution. Preserve the original exception type and traceback, including the script's template location.
- Undefined names follow the appropriate Python or Jinja behavior rather than being swallowed by blanket exception handling.

## Validation

Retain and adapt the existing tests: errors caused by script execution move from `from_string()` to `render()`. Add behavior-focused coverage for:

- Variables, functions, classes, imports, indentation, whitespace control, empty scripts, and comment-only scripts.
- Source-aware syntax and runtime errors, invalid names, duplicate declarations, and nested Jinja rejection.
- No execution during compilation; conditionals, loops, local bindings, and no forward references.
- Fresh state across repeated and concurrent renders and no environment-global pollution.
- Both import forms, aliases, context modes, independent imports, nested imports, and imports from mixed-content templates.
- Repeated includes, same-name scripts in caller and include, inheritance overrides, and `super()`.
- Caller-owned object mutation versus extension-owned state isolation.
- Bytecode cache reuse and standard macro imports in extension-enabled environments.
- Installation from built wheel and source distribution and executable documentation examples.

Proposed support baseline: Python 3.10+ and Jinja 3.1.x. Validate the minimum supported versions and current supported stable releases when configuring CI. Async Python inside scripts is out of scope; ordinary synchronous scripts in Jinja async rendering should be covered if the import integration has async paths.

## Packaging, documentation, and migration

Move package metadata and build configuration into `pyproject.toml`, remove redundant legacy configuration, declare dependency bounds, and ensure artifacts contain only intended package files. Preserve package and import names. Verify the declared BSD license against repository history before adding license text; do not invent missing license terms.

Update README and examples to cover rendering, reusable helpers, aliases, context, state lifetime, errors, and the trusted-template execution model. Executing Python is not a sandbox; Jinja sandbox settings must not be represented as restricting script code.

Document this as a breaking behavior change: execution occurs during rendering, state no longer persists between renders, duplicate declarations fail, and helpers are imported explicitly instead of appearing in environment globals. Include before/after migration examples. Publishing a release is outside this refactor.

## Alternatives considered

- Environment-global script names: rejected because unrelated templates and renders interfere.
- Unnamed script blocks: rejected for this refactor because explicit namespaces are a core user requirement.
- A dedicated script-import tag: fallback only after user review; standard Jinja syntax is preferred.
- Forcing imports to use caller context: rejected because freshness and context visibility are separate requirements.

## Review and handoff

Review this written design before creating the implementation plan. After approval, use the writing-plans skill to specify the import feasibility task, concrete module changes, regression coverage, packaging work, and execution method. No product implementation or dependency installation belongs to this design stage.
