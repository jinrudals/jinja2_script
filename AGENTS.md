# AGENTS.md

Guidance for AI agents working in this repository.

## Project

`jinja-script-block` is a Jinja2 extension that adds `{% script name %}...{% endscript %}`
blocks. Scripts run at render time and expose a named Python namespace to templates.
Package: `jinja_script_block/` (flat layout). Python >= 3.10, Jinja2 >= 3.1, < 3.2.

## Harness docs (read first)

Project knowledge for agents lives in `docs/harness/`. Before starting a task, read:

- `docs/harness/*.md`
- `docs/harness/**/*.md`

Treat these as the source of truth for architecture, testing, and release rules.
If a task changes behavior they describe, update them in the same commit.
`docs/superpowers/` holds historical design material; it is reference only.

## Language

All agent-facing documents (this file, `docs/harness/**`, plans, specs) are written in English.
User-facing text (README, CHANGELOG, docstrings, error messages) is also English.

## Git workflow

- Never commit directly to `main`; use a git worktree: `git worktree add .worktrees/<dir> -b <branch>`.
- Follow the Angular commit convention: `<type>(<scope>): <subject>`.
  - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
  - Subject: imperative, lower case, no trailing period, <= 72 chars.
  - Body explains *why*; footer holds `BREAKING CHANGE:` and issue references.
- Branch names: `<type>/<short-description>` (e.g. `feat/pypi-release`).
- Keep commits atomic; do not mix refactors with behavior changes.

## Commands

```sh
python -m venv .venv && .venv/bin/python -m pip install -e . build ruff mypy
.venv/bin/python -m unittest discover -v
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy jinja_script_block
.venv/bin/python -m build && .venv/bin/python tools/check_dist.py
```

All of these must pass before a change is considered done.

## Rules

- Tests use `unittest`, live in `tests/`, and accompany every behavior change or bug fix.
- Keep the public API in `jinja_script_block/__init__.py` (`__all__`) minimal and typed.
- Do not add runtime dependencies beyond Jinja2 without discussion.
- Version lives in two places: `pyproject.toml` and `jinja_script_block/__init__.py`; keep them in sync.
- Update `CHANGELOG.md` for every user-visible change.
- Never commit secrets, tokens, or build output (`dist/`, `build/`, `*.egg-info/`).
