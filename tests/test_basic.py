import unittest
from jinja2 import Environment
from jinja2.exceptions import UndefinedError
from script import FunctionExtension, NoModuleNameDefined, CompileError

class ExtensionUnitTest(unittest.TestCase):
  def setUp(self):
    self.env = Environment(extensions=[FunctionExtension])
  def test_fail_when_no_module_is_defiend(self):
    with self.assertRaises(NoModuleNameDefined):
      self.env.from_string("""
      {% script %}
      test
      {% endscript %}
      """)
  def test_fail_when_compiled_error(self):
    with self.assertRaises(CompileError):
      self.env.from_string('''
      {%-script test%}
      import re
      {%-endscript-%}
      ''')
  def test_compile_success(self):
      self.env.from_string('''
      {%-script test -%}
      import re
      {%-endscript-%}
      ''')
      self.assertTrue(True)

  def test_fail_when_unknown_module_called(self):
    with self.assertRaises(UndefinedError):
      temlate = self.env.from_string('''
{%-script test -%}
import re
def test1(): return None
{%-endscript-%}
      {{test1.test1()}}
      ''')
      temlate.render()
  def test_success_when_calling(self):
    template = self.env.from_string('''
{%-script test -%}
import re
def test1(): return None
{%-endscript-%}
{{test.test1()}}
    ''')
    self.assertEqual(template.render().strip(), "None")

  def test_success_when_calling_multiple(self):
    template = self.env.from_string('''
{%-script test -%}
def test1(): return True
def test2(): return False
{%-endscript-%}
{{test.test1()}}
{{test.test2()}}
    ''')
    self.assertEqual(template.render().strip(), "True\nFalse")
  def test_multiple_module(self):
    template = self.env.from_string('''
{%-script test-%}
def test1():
  return "Test"
{%- endscript -%}
{%-script test1-%}
def test1():
  return "Test1"
{%- endscript -%}
{{test.test1()}}
{{test1.test1()}}
    ''')
    self.assertEqual(template.render().strip(), "Test\nTest1")
  def test_import_usage(self):
    template = self.env.from_string('''
{%-script test -%}
import re
def test1(string1):
  pattern = re.compile('[a-z]')
  return pattern.findall(string1)
def test2(): return False
{%-endscript-%}
{{test.test1('abc')}}
    ''')
    rendered = template.render()
    value = eval(rendered.strip())
    self.assertTrue(isinstance(value, list))
    self.assertEqual(value, ['a', 'b', 'c'])
  def test_variable_set(self):
    template = self.env.from_string('''
{%script test%}
x = 3
y = 4
def set_x(value):
  global x
  x = value
  return ''
{% endscript %}
{{test.set_x(1)}}{{test.x}}
    ''')
    rendered = template.render().strip()
    self.assertNotEqual(rendered, "3")
    self.assertEqual(rendered, "1")

  def test_variable_set_at_render(self):
    template = self.env.from_string('''
{%script test%}
x = 3
y = 4
def set_x(value):
  global x
  x = value
  return ''
{% endscript %}
{{test.set_x(x)}}{{test.x}}
    ''')
    rendered = template.render(x=7).strip()
    self.assertNotEqual(rendered, "3")
    self.assertEqual(rendered, "7")
  def test_class_instance(self):
    template = self.env.from_string('''
{% script test%}
class MyModule:
  def __init__(self, key):
    self.key = key
  def __str__(self):
    return f'Module Has {self.key}'
{% endscript%}
{{test.MyModule(1)}}
    ''')
    rendered = template.render().strip()
    self.assertEqual(rendered, 'Module Has 1')

  def test_class_member_append(self):
    template = self.env.from_string('''
{% script test%}
class MyModule:
  containers = []

{% endscript%}
{% set container = test.MyModule.containers %}
{% if container.append(3) == None %}{% endif %}
{{container}}
    ''')
    rendered = template.render().strip()
    print(rendered)
    self.assertEqual(rendered, '[3]')


