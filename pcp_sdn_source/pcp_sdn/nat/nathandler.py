"""
This module:
* installs the flow tables to the NAT forwarder
* installs flow table entries to the NAT forwarder
"""

#===============================================================================

from . import nattable
from . import natinstaller

import logging

#===============================================================================


class MappingRemovalType(object):
  REMOVAL_TYPES = FLOW_ENTRY_REMOVED_BY_FORWARDER, REQUESTED_BY_CLIENT = (0, 1)


class MappingError(Exception):
  pass


#===============================================================================


class NatHandler(object):
  
  def __init__(self, forwarder, external_port, table_ids, next_table_id):
    self._nat_installer = natinstaller.NatInstaller(forwarder, external_port, table_ids, next_table_id)
    self._nat_table = nattable.NatTable()
  
  def create_mapping(self, internal_ip, internal_port, external_ip, external_port, protocol, lifetime):
    """
    Create mapping entry.
    
    If the mapping entry for the internal IP and port already exists, raise
    `MappingError`. To update lifetime of a mapping entry, use
    `update_mapping_lifetime` instead.
    
    Further restrictions apply according to the `NatTable.add_entry` method.
    """
    
    table_entry = self._nat_table.find_entry(internal_ip, internal_port)
    if table_entry:
      raise MappingError("Mapping entry already exists: {0}"
                         .format(table_entry))
    else:
      table_entry = self._nat_table.add_entry(
        internal_ip, internal_port, lifetime, external_ip, external_port, protocol)
      self._nat_installer.install_nat_entry(table_entry)
      
      mapping = table_entry.to_dict()
      logging.info("Created mapping entry: {0}".format(mapping))
      
      return mapping
  
  def find_mapping(self, internal_ip, internal_port):
    """
    Return the mapping entry given the internal IP address and internal port.
    
    If the mapping entry does not exist, return None.
    """
    
    table_entry = self._nat_table.find_entry(internal_ip, internal_port)
    
    if table_entry:
      return table_entry.to_dict()
    else:
      return None
  
  def update_mapping_lifetime(self, internal_ip, internal_port, lifetime):
    """
    Update lifetime of the existing mapping entry. Return the mapping entry.
    
    If the mapping entry does not exist, raise `MappingError`.
    """
    
    table_entry = self._nat_table.find_entry(internal_ip, internal_port)
    
    if table_entry:
      table_entry = self._nat_table.update_entry_lifetime(internal_ip, internal_port, lifetime)
      self._nat_installer.modify_nat_entry_lifetime(table_entry)
      
      mapping = table_entry.to_dict()
      logging.info("Updated mapping entry lifetime: {0}".format(mapping))
      
      return mapping
    else:
      raise MappingError("Mapping entry '{0}, {1}' does not exist"
                         .format(internal_ip, internal_port))
  
  def remove_mapping(self, internal_ip, internal_port,
    mapping_removal_type=MappingRemovalType.FLOW_ENTRY_REMOVED_BY_FORWARDER):
    """
    Remove mapping entry.
    
    Upon successful removal, return True. If no mapping entry is found, return
    False.
    
    If `mapping_removal_type` is `MappingRemovalType.REQUESTED_BY_CLIENT`,
    remove flow entries in the NAT forwarder. Otherwise, it is assumed that the
    flow entries expired or were removed by other means.
    """
    
    table_entry = self._nat_table.find_entry(internal_ip, internal_port)
    if table_entry is None:
      logging.info("Mapping entry not removed (mapping does not exist): {0}, {1}"
                   .format(internal_ip, internal_port))
      return False
    else:
      if mapping_removal_type == MappingRemovalType.REQUESTED_BY_CLIENT:
        self._nat_installer.uninstall_nat_entry(table_entry)
      
      self._nat_table.remove_entry(internal_ip, internal_port)
      
      logging.info("Removed mapping entry: {0}".format(table_entry))
      
      return True
    