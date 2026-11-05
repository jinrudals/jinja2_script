# Changelog

## 0.1.0

### Changed

- Scripts now execute during rendering, in the order their declarations are reached, and state is fresh per render. See the README's migration section.
- Compile-time errors use a consistent hierarchy: `ScriptBlockError` (a `jinja2.TemplateSyntaxError`) with `ScriptNameError` and `ScriptSyntaxError`. Invalid and duplicate script names now raise `ScriptNameError`.

### Added

- Type hints and a `py.typed` marker.
- `jinja_script_block.__version__`.
- MIT `LICENSE`, PyPI classifiers and project URLs.

### Deprecated

- `NoModuleNameDefined` (use `ScriptNameError`), `NoInternalJinjaAccepted` and `CompileError` (use `ScriptSyntaxError`). The old names still import and emit a `DeprecationWarning`.
