"""Import a namespace using either of Jinja's standard import forms."""

from jinja2 import DictLoader, Environment

from jinja_script_block import ScriptBlockExtension


def main():
    env = Environment(
        loader=DictLoader(
            {
                "pricing": "{% script pricing %}\ndef total(items):\n    return sum(items)\n{% endscript %}",
                "page": '{% from "pricing" import pricing %}{{ pricing.total(items) }}',
                "module_page": '{% import "pricing" as helpers %}{{ helpers.pricing.total(items) }}',
            }
        ),
        extensions=[ScriptBlockExtension],
    )
    result = env.get_template("page").render(items=[3, 4])
    assert env.get_template("module_page").render(items=[3, 4]) == result
    print(result)


if __name__ == "__main__":
    main()
