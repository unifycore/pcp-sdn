"""
This module:
* defines a generic class to store payload data
"""

#===============================================================================


class Message(object):
  
  """
  This class can be used to store payload data.
  """
  
  def __init__(self):
    self._fields = {}
  
  def __getitem__(self, field_name):
    try:
      return self._fields[field_name]
    except KeyError:
      raise KeyError("invalid message field: '{0}'".format(field_name))
  
  def __setitem__(self, field_name, field_value):
    self._fields[field_name] = field_value
  
  def __delitem__(self, field_name):
    del self._fields[field_name]
  
  def __contains__(self, field_name):
    return field_name in self._fields
  
  def __iter__(self):
    for field_name in self._fields.keys():
      yield field_name
  
  def values(self):
    for field_value in self._fields.values():
      yield field_value
  
  def items(self):
    for field_name, field_value in self._fields.items():
      yield field_name, field_value
  
  def update(self, fields):
    self._fields.update(fields)
  
  def parse(self, data):
    pass
  
  def serialize(self):
    pass


#===============================================================================


class MessageParseError(Exception):
  pass


class MessageSerializationError(Exception):
  pass

