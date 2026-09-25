"""Run with python -m examples.basic from the project directory."""

from jinja2 import Environment

from jinja_script_block import ScriptBlockExtension


def main():
    env = Environment(extensions=[ScriptBlockExtension])
    template = env.from_string("""
{%- script data %}
containers = []
value = 333
{% endscript -%}
{%- script helpers %}
def add(obj):
    obj.append(3)
{% endscript -%}
{%- set _ = data.containers.append('1') -%}
{%- set _ = helpers.add(data.containers) -%}
{{ data.containers }}
{{ data.value }}
""")
    print(template.render())


if __name__ == "__main__":
    main()
