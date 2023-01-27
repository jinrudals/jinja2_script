# Jinja2 Script

## Introduction
In ERB, custom functions can be written in the template. However with jinja2, the functions should be written in python, and must be included in the rendering environment.

## Use Script Block
```jinja2
{% script modulename %}
  # Your Python Code that should be in .py
{% endscript %}
```
Define your python codes in script block. This is compiled before actual run starts.

To use compiled block, do it as following:
```
{{module.functions_you_defined()}}
{{module.values_you_defined()}}
{{module.function_with_arguments(1)}}
{{module.function_with_arguments_at_render(x)}}
```

## How to use
```python3
from jinja_script_block import ScriptBlockExtension
from jinja2 import Environment

env = Environment(extensions=[ScriptBlockExtension])

env.from_string('''
{% script mymodule %}
class MyClass:
  containers = []
{% endscript%}
''')
```
