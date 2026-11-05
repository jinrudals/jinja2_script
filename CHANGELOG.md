# Changelog

## 0.1.0

### Changed

- Scripts now execute during rendering, in the order their declarations are reached, and state is fresh per render. See the README's migration section.
- Compile-time errors use a consistent hierarchy: `ScriptBlockError` (a `jinja2.TemplateSyntaxError`) with `ScriptNameError` and `ScriptSyntaxError`. Invalid and duplicate script names now raise `ScriptNameError`.
- Clearer diagnostics: invalid-name errors explain why; duplicate-name errors give the template and both declaration lines; Python syntax errors name the script and report the template line and column; an unterminated or stray `{% endscript %}` raises `ScriptBlockError` with the opening line; extra tokens in `{% script %}` raise `ScriptNameError`; deprecation warnings state the replacement class and removal plan.

### Added

- Type hints and a `py.typed` marker.
- `jinja_script_block.__version__`.
- MIT `LICENSE`, PyPI classifiers and project URLs.

### Deprecated

- `NoModuleNameDefined` (use `ScriptNameError`), `NoInternalJinjaAccepted` and `CompileError` (use `ScriptSyntaxError`). The old names still import and emit a `DeprecationWarning`.
