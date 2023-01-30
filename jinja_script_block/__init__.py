import jinja2

from jinja2.ext import Extension, nodes
from jinja2 import Environment
from types import FunctionType, ModuleType
import re


_pattern = re.compile('\n(\s*)\w')
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
        lines = data[0].nodes[0].data
        if not lines.startswith('\n'):
          lines = '\n' + lines
        target = len(_pattern.findall(lines)[0])
        pattern = re.compile(r'\n\s{}'.format("{" + f'0,{target}' + "}"))
        lines = pattern.sub('\n', lines)
        data = compile(lines, "<string>", "exec")
      except:
        raise CompileError()
      mod = ModuleType(name)
      exec(data, mod.__dict__)
      self.environment.globals[name] = mod
      return nodes.Scope([])
