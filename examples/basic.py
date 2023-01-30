from jinja_script_block import ScriptBlockExtension
from jinja2 import Environment

env = Environment(extensions=[ScriptBlockExtension])

template = env.from_string('''
  {%- script myblock %}   
  containers = []
  value = 333
  {% endscript -%}

  {%- script myblock2 %}
  def add(obj):
    obj.append(3)
  def function(value):
    if value == "xx":
      return ''
  {% endscript -%}

{%- set _=myblock.containers.append('1') -%}
{%- set _=myblock2.add(myblock.containers) -%}

{{myblock.containers}}
{{myblock.value}}
''')
rendered = template.render()
print(rendered)