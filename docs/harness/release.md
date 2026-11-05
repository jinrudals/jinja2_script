# Release

PyPI project: `jinja-script-block` (existing releases 0.0.2–0.0.4).

## Checklist

1. Bump the version in `pyproject.toml` and `jinja_script_block/__init__.py`.
2. Move the `CHANGELOG.md` entry from Unreleased to the new version.
3. Run every command in `AGENTS.md#commands`; all must pass.
4. Optionally run the `publish` workflow manually (workflow_dispatch) to upload to TestPyPI.
5. Publish a GitHub Release tagged `vX.Y.Z`; the `publish` workflow uploads to PyPI.

## Notes

- Publishing uses PyPI trusted publishing (OIDC); no API tokens are stored.
  The trusted publisher (owner `jinrudals`, repo `jinja2_script`, workflow `publish.yml`,
  environment `pypi`; and `testpypi` for TestPyPI) must be configured on pypi.org.
- Versions are immutable on PyPI; a bad release requires a new version.
- Follow SemVer. Pre-1.0: minor bumps may contain breaking changes (document them).
