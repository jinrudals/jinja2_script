# Testing

- Framework: `unittest` (stdlib); run `python -m unittest discover -v`.
- Layout: `tests/test_<area>.py` (basic, composition, imports, lifecycle, runtime, source).
- Every behavior change or bug fix needs a test that fails without it.
- CI matrix: Python 3.10–3.14 x Jinja2 3.1.0 (minimum) and latest 3.1.x.
- `tools/check_dist.py` installs the built wheel/sdist in a clean venv and smoke-tests it;
  it guards against packaging mistakes (missing files, importing from the source tree).
- Examples in `examples/` run in CI (`python -m examples.basic`, `python -m examples.reuse`).
- Lint/type gates: `ruff check`, `ruff format --check`, `mypy jinja_script_block`.
