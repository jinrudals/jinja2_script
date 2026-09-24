# Jinja2 Script

Define named Python helpers inside Jinja templates and reuse them through ordinary Jinja imports. Script code executes during rendering, in the order its declarations are reached, similar to ERB's embedded scripting.

Requires Python 3.10+ and Jinja 3.1.x. Version 0.1 changes execution timing and state lifetime from 0.0.4; see [migration](#migrating-from-004).

## Installation

Install this checkout:

```sh
python -m pip install .
```

Enable the extension:

```python
from jinja2 import Environment
from jinja_script_block import ScriptBlockExtension

env = Environment(extensions=[ScriptBlockExtension])
template = env.from_string("""
{% script pricing %}
def total(items):
    return sum(items)
{% endscript %}
Total: {{ pricing.total(items) }}
""")
print(template.render(items=[3, 4]).strip())  # Total: 7
```

The string `"jinja_script_block.ScriptBlockExtension"` also works in the extensions list.

## Names and execution

```jinja2
{% script formatting %}
import decimal

def currency(value):
    return f"${decimal.Decimal(value):.2f}"
{% endscript %}

{{ formatting.currency("12.5") }}
```

Each script declares one public Python identifier. Names starting with `_` and Python keywords are rejected. A name may be declared only once per source template, including declarations in different branches, macros, or blocks. Different templates may use the same name.

Scripts support normal Python functions, classes, imports, and variables. Empty and comment-only scripts are valid. Common indentation is removed; relative Python indentation is preserved. Python strings may contain Jinja delimiters, but a literal `{% endscript %}` terminates the block even inside a Python string. Nested Jinja statements are not evaluated inside Python.

Scripts emit no template output. Use `{{ name.value }}` to render a result; Jinja's normal escaping applies. `print()` remains normal Python output to stdout.

Declarations execute when reached. A skipped conditional does not execute its script. A loop creates a fresh namespace for each iteration. The namespace becomes available after its declaration and follows Jinja scope: loop-, macro-, and block-local names do not become global exports.

Scripts can read render inputs and visible local variables, including macro arguments and loop metadata:

```jinja2
{% for item in items %}
  {% script row %}
  label = f"{loop.index}: {item}"
  {% endscript %}
  {{ row.label }}
{% endfor %}
```

Python assignments change the script namespace, not Jinja's surrounding bindings. The context snapshot is shallow: mutating a list supplied by the caller still mutates that list. Imported Python modules retain Python's ordinary module caching and global state.

## Reuse helpers from another template

A file can contain only scripts:

```jinja2
{# scripts/pricing.jinja #}
{% script pricing %}
def total(items):
    return sum(items)
{% endscript %}
```

Import its namespace:

```jinja2
{% from "scripts/pricing.jinja" import pricing %}
{{ pricing.total(items) }}
```

Or import the template module:

```jinja2
{% import "scripts/pricing.jinja" as helpers %}
{{ helpers.pricing.total(items) }}
```

Aliases distinguish helpers from different files:

```jinja2
{% from "scripts/retail.jinja" import pricing as retail %}
{% from "scripts/wholesale.jinja" import pricing as wholesale %}
{{ retail.total(items) }} / {{ wholesale.total(items) }}
```

An import constructs the source template's exports and does not emit its rendered text into the caller. Templates containing both scripts and content can therefore provide helpers, but their other top-level code still executes and can require inputs. Helper-only files are the simplest reusable libraries. Only executed top-level declarations are exported.

Normal Jinja import context rules apply. Imports without context do not receive ordinary render inputs. Add `with context` when initialization needs caller variables:

```jinja2
{% from "scripts/pricing.jinja" import pricing with context %}
```

Prefer explicit function arguments for reusable helpers. Environment and template globals follow Jinja's existing rules, including propagation of a template-specific global key's current context value when a render argument overrides it.

Each import execution creates fresh script state. Two independent imports of the same file create independent instances; repeated calls through one alias share that instance. Ordinary Jinja alias rebinding remains allowed; duplicate validation applies to script declarations.

### Includes and inheritance

`include` renders content; it does not export script names to the caller. An included file's script declaration creates a local namespace even when the caller already has a script with the same name. Repeated includes, including `without context`, execute their scripts afresh.

`extends` and `super()` follow Jinja's block execution and scope rules. Scripts in overridden blocks execute only when those blocks run. Same-named block-local scripts do not overwrite each other. There is no extra globally addressable namespace per inheritance file; import shared helpers explicitly where needed.

## State and integration

Fresh renders, imports, and includes do not share extension-created mutable namespaces. Immutable compiled Python code is cached with a bounded lifetime. Objects supplied explicitly by the application and ordinary Python modules are outside this isolation guarantee.

The extension composes an environment-local Template mixin. It observes module creation and bypasses Jinja's module cache only when creation executes scripts, including through nested imports. Ordinary macro-only modules retain caching. This also works when templates load from a bytecode cache and during async rendering of synchronous script code.

This integration depends on Jinja 3.1's `_get_default_module` and `_get_default_module_async` hooks; dependency bounds intentionally exclude Jinja 3.2 until tested. Environment overlays and custom public `Template.make_module` / `make_module_async` methods are supported. Custom overrides of those two private default-module hooks conflict with this integration. Configure the extension before loading templates.

## Errors and trusted code

Invalid Python, missing names, duplicate declarations, and malformed blocks fail at template compilation with a template name and line. Runtime exceptions occur during rendering or import execution, retaining their Python exception type and source location.

`CompileError`, `NoModuleNameDefined`, and `NoInternalJinjaAccepted` remain importable for compatibility and now participate in Jinja's `TemplateSyntaxError` hierarchy.

Script blocks execute arbitrary trusted Python. They are not a sandbox, and Jinja's `SandboxedEnvironment` does not restrict them. Python `await` syntax inside script blocks is unsupported; use ordinary synchronous scripts even with Jinja's `render_async()`.

## Migrating from 0.0.4

This is a breaking behavior change:

- Scripts execute during rendering, not template loading.
- Script-created state is fresh on each render and import execution.
- Script modules are no longer written into `env.globals`.
- Duplicate declarations within one source template fail at compilation.
- Public script names cannot start with `_` or be Python keywords.

Previously, loading a helper file implicitly installed environment globals:

```python
# Old behavior: loading the file was enough to install helpers globally.
env.get_template("scripts/pricing.jinja")
result = env.get_template("page.jinja").render(items=[3, 4])
```

Now add an explicit import in `page.jinja`:

```jinja2
{% from "scripts/pricing.jinja" import pricing %}
{{ pricing.total(items) }}
```

Previously, initialization failures appeared during `from_string()` or `get_template()`. Catch runtime failures around rendering instead:

```python
template = env.from_string("{% script work %}\nvalue = 1 / divisor\n{% endscript %}")
try:
    template.render(divisor=0)
except ZeroDivisionError:
    pass
```

Syntax errors still occur when compiling the template. If persistent state is intentional, own it in the application and pass it explicitly; do not rely on a script namespace surviving a render. Clear old template bytecode caches when upgrading from 0.0.4, because cached templates contain the old execution behavior.

## Development

```sh
python -m venv .venv
.venv/bin/python -m pip install -e . build ruff
.venv/bin/python -m unittest discover -v
.venv/bin/python -m examples.basic
.venv/bin/python -m examples.reuse
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m build
```

CI runs Python 3.10–3.14 with minimum and current Jinja 3.1 versions, and checks both built distributions. Python 3.14's stable release is documented by [Python.org](https://www.python.org/downloads/release/python-3140/); Jinja's supported series is documented in its [release history](https://jinja.palletsprojects.com/en/stable/changes/).

The original package metadata declares BSD, but the repository history contains no license file specifying the variant. That metadata is retained without inventing license terms.
