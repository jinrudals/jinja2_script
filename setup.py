from setuptools import setup, find_packages

from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="jinja-script-block",
    version="0.0.4",
    author="Benjamin Jin",
    author_email="jinrudals135@naver.com",
    license="BSD",
    url="https://github.com/jinrudals/jinja2_script.git",
    package_dir={"jinja_script_block":"jinja_script_block"},
    install_requires=['Jinja2'],
    long_description=long_description,
    long_description_content_type='text/markdown',
)