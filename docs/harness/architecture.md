# Architecture

Package `jinja_script_block/`:

| Module | Responsibility |
|--------|----------------|
| `extension.py` | `ScriptBlockExtension`: parses `{% script %}` and emits render-time nodes |
| `source.py` | Script source handling: dedent, name validation, duplicate detection |
| `compiler.py` | Compiles script code; immutable compiled code is cached with a bounded lifetime |
| `runtime.py` | Executes scripts per render and builds fresh namespaces |
| `integration.py` | Integration with Jinja scoping, imports, includes, inheritance |
| `errors.py` | `ScriptBlockError`, `ScriptNameError`, `ScriptSyntaxError`, deprecation errors |

## Invariants

- Scripts execute when their declaration is reached during rendering, never at compile time.
- Renders, imports, and includes never share extension-created mutable namespaces.
- Script names: public identifiers only; unique per source template.
- Scripts emit no template output.
- Public API is exactly what `__init__.__all__` exports.

Historical design: `docs/superpowers/specs/`.
