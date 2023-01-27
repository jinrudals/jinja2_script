import jinja2

from jinja2.ext import Extension, nodes
from jinja2 import Environment
from types import FunctionType, ModuleType
import re

_pattern = re.compile('(\s*).*')
class NoInternalJinjaAccepted(Exception):
  def __init__(self):
    pass
  def __str__(self) -> str:
    return f"Currently No Jinja Script is allowd in the script block"
class NoModuleNameDefined(Exception):
  def __str__(self) -> str:
    return "Need to define Module Name"

class CompileError(Exception):
  def __str__(self):
    return "Compile Failure. Check your script block"

class ScriptBlockExtension(Extension):
    tags = {'script'}
    def __init__(self, environment: Environment) -> None:
        super().__init__(environment)

    def parse(self, parser):
      parser.parse_expression()
      try:
        name = parser.stream.expect('name').value
      except:
        raise NoModuleNameDefined()
      data = parser.parse_statements(('name:endscript',), drop_needle=True)

      if len(data) > 1:
        raise NoInternalJinjaAccepted()

      try:
        data = [each for each in data[0].nodes[0].data.split('\n') if each.strip() != '']
        matched = _pattern.match(data[0]).group(1)
        data = '\n'.join([each.replace(matched, '',1) for each in data])
        data = compile(data, "<string>", "exec")
      except:
        raise CompileError()
      mod = ModuleType(name)
      exec(data, mod.__dict__)
      self.environment.globals[name] = mod
      return nodes.Scope([])
