"""Build-artifact smoke checks, executed outside the source checkout."""

import argparse
import os
import subprocess
import tarfile
import tempfile
import venv
import zipfile
from pathlib import Path

SMOKE = """
from pathlib import Path
from jinja2 import Environment, DictLoader
import jinja_script_block
from jinja_script_block import ScriptBlockExtension
assert Path(jinja_script_block.__file__).is_relative_to(Path(__import__('sys').prefix))
env = Environment(loader=DictLoader({
    "lib": "{% script s %}\\nvalues=[]\\n{% endscript %}",
    "page": '{% from "lib" import s %}{% set _=s.values.append(1) %}{{ s.values|length }}',
}), extensions=[ScriptBlockExtension])
template = env.from_string("{% script demo %}\\nvalue=7\\n{% endscript %}{{ demo.value }}")
assert template.render() == template.render() == "7"
page = env.get_template("page")
assert page.render() == page.render() == "1"
print("Installed artifact: direct scripts and isolated imports OK")
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", nargs="?", default="dist")
    args = parser.parse_args()
    directory = Path(args.dist).resolve()
    wheels = list(directory.glob("*.whl"))
    sdists = list(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit("Expected exactly one wheel and one source distribution")
    with zipfile.ZipFile(wheels[0]) as archive:
        names = archive.namelist()
        assert "jinja_script_block/extension.py" in names
        assert not any(name.startswith(("tests/", "examples/")) for name in names)
    with tarfile.open(sdists[0]) as archive:
        assert any(name.endswith("/pyproject.toml") for name in archive.getnames())
    for artifact in [wheels[0], sdists[0]]:
        with tempfile.TemporaryDirectory(prefix="jinja-script-artifact-") as temporary:
            root = Path(temporary)
            venv.EnvBuilder(with_pip=True).create(root / "env")
            python = (
                root
                / "env"
                / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            )
            subprocess.run(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    "--cache-dir",
                    str(Path(tempfile.gettempdir()) / "jinja-script-pip-cache"),
                    str(artifact),
                ],
                cwd=root,
                check=True,
            )
            subprocess.run([str(python), "-c", SMOKE], cwd=root, check=True)
            print(f"{artifact.name}: PASS", flush=True)


if __name__ == "__main__":
    main()
