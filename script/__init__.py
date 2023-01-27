import jinja2

from jinja2.ext import Extension, nodes
from jinja2 import Environment
from types import FunctionType, ModuleType

import re

class TooManyFunctionsDefined(Exception):
  def __init__(self, length):
    self.lenth = length
  def __str__(self) -> str:
    return f"Cunnently Only One Function should be defined in script"
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

class FunctionExtension(Extension):
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
        data = compile(data[0].nodes[0].data, "<string>", "exec")
      except:
        raise CompileError()
      mod = ModuleType(name)
      exec(data, mod.__dict__)
      self.environment.globals[name] = mod
      return nodes.Scope([])
