"""
This module defines the NAT table and its entries.
"""

#===============================================================================

import netaddr

from ..app_config import app_config

#===============================================================================


class AddressFamily(object):
  ADDRESS_FAMILIES = IPv4, IPv6 = (0x0800, 0x86DD)


class IpUpperProtocol(object):
  PROTOCOLS = TCP, UDP = (0x06, 0x11)


class NatTableAllocationType(object):
  TYPES = ROUND_ROBIN, RANDOM = (0, 1)


#===============================================================================


class NatTable(object):
  
  """
  This class:
  * contains a table of ((internal IP address, internal port), NAT table entry)
  pairs
  * can add, find and remove table entries
  """
  
  # FIXME: For now, only `ROUND_ROBIN` is implemented for both external IP and
  # port allocation.
  
  def __init__(self, **nat_pool_config):
    """
    Create a NAT table.
    
    `**nat_pool_config` contains configuration parameters for the NAT pool. The
    NAT pool contains the following parameter names:
    
      * 'internal_ip_low_end'
      * 'internal_ip_high_end'
      * 'internal_port_low_end'
      * 'internal_port_high_end'
      * 'external_ip_low_end'
      * 'external_ip_high_end'
      * 'external_port_low_end'
      * 'external_port_high_end'
      * 'ip_allocation_type'
      * 'port_allocation_type'
    
    Default values are taken from the configuration file (`app_config` module).
    """
    
    # Key: Internal IP + internal port
    # Value: NatTableEntry
    self._table = {}
    
    # Key: External IP + external port
    # Value: NatTableEntry (the same entry as in `self._table` for the
    # corresponding internal IP and internal port)
    self._table_external = {}
    
    # Make a copy to be able to modify it.
    self._nat_pool_config = dict(app_config['default_nat_pool_config'])
    
    for config_param_name, value in nat_pool_config.items():
      if config_param_name not in self._nat_pool_config:
        raise TypeError("invalid keyword argument '{0}'".format(config_param_name))
      self._nat_pool_config[config_param_name] = value
    
    # Key: external IP address
    # Value: last port allocated
    self._allocated_external_ips_and_ports = {}
    
    self._last_external_ip = self._nat_pool_config['external_ip_low_end']
  
  def add_entry(self, internal_ip, internal_port, lifetime, external_ip=None, external_port=None,
                protocol=IpUpperProtocol.UDP, address_family=AddressFamily.IPv4):
    """
    Add a new entry to the NAT table.
    
    If `external_ip` is one of the following:
      
      * None
      * empty string
      * "all zeros" IP address ("::" or "0.0.0.0"),
      * IP address outside the NAT pool of external IP addresses
      
    then allocate an external IP address from the NAT pool. Otherwise, use the
    specified IP address.
    
    If `external_port` is one of the following:
    
      * None
      * empty string
      * 0
      * port outside the NAT pool of external ports
    
    then allocate an external port from the NAT pool. Otherwise, use the
    specified port.
    
    If the specified combination of `external_ip` and `external_port` is
    already in use, allocate an IP address and port from the NAT pool.
    """
    
    # Use None as the unspecified value.
    if not external_ip:
      external_ip = None
    else:
      external_ip_netaddr = netaddr.IPAddress(external_ip)
      if external_ip_netaddr.is_ipv4_mapped():
        external_ip_netaddr = external_ip_netaddr.ipv4()
      if external_ip_netaddr.value == 0:
        external_ip = None
      
      if (external_ip < self._nat_pool_config['external_ip_low_end'] or
          external_ip > self._nat_pool_config['external_ip_high_end']):
        external_ip = None
    
    # Use None as the unspecified value.
    if not external_port:
      external_port = None
    else:
      if (external_port < self._nat_pool_config['external_port_low_end'] or
          external_port > self._nat_pool_config['external_port_high_end']):
        external_port = None
    
    if self.find_entry_by_external(external_ip, external_port):
      external_ip = None
      external_port = None
    
    external_ip, external_port = self._allocate_entry(external_ip, external_port)
    
    nat_table_entry = NatTableEntry(address_family, protocol,
      internal_ip, internal_port, external_ip, external_port, lifetime)
    
    self._add_entry(nat_table_entry)
    
    return nat_table_entry
  
  def find_entry(self, internal_ip, internal_port):
    """
    Find table entry by the specified internal IP and internal port.
    """
    
    try:
      entry = self._table[self._get_key(internal_ip, internal_port)]
    except KeyError:
      entry = None
    
    return entry
  
  def find_entry_by_external(self, external_ip, external_port):
    """
    Find table entry by the specified external IP and external port.
    """
    
    try:
      entry = self._table_external[self._get_key(external_ip, external_port)]
    except KeyError:
      entry = None
    
    return entry
  
  def update_entry_lifetime(self, internal_ip, internal_port, lifetime):
    """
    Update the lifetime of the table entry. Return the updated entry.
    """
    
    entry = self._table[self._get_key(internal_ip, internal_port)]
    
    entry_dict = entry.to_dict()
    entry_dict['lifetime'] = lifetime
    
    new_entry = NatTableEntry(**entry_dict)
    self._table[self._get_key(internal_ip, internal_port)] = new_entry
    self._table_external[self._get_key(entry.external_ip, entry.external_port)] = new_entry
    
    return new_entry
  
  def remove_entry(self, internal_ip, internal_port):
    entry = self.find_entry(internal_ip, internal_port)
    if entry is not None:
      del self._table[self._get_key(internal_ip, internal_port)]
      del self._table_external[self._get_key(entry.external_ip, entry.external_port)]
  
  def remove_entry_by_external(self, external_ip, external_port):
    entry = self.find_entry_by_external(external_ip, external_port)
    if entry is not None:
      del self._table[self._get_key(entry.internal_ip, entry.internal_port)]
      del self._table_external[self._get_key(external_ip, external_port)]
  
  def _allocate_entry(self, external_ip, external_port):
    if external_ip is None and external_port is None:
      ip, port = self._allocate_ip_and_port()
      return ip, port
    elif external_ip is not None and external_port is None:
      ip, port = self._allocate_ip_and_port(external_ip)
      return ip, port
    elif external_ip is None and external_port is not None:
      ip = self._allocate_ip()
      return ip, external_port
    elif external_ip is not None and external_port is not None:
      return external_ip, external_port
  
  def _allocate_ip_and_port(self, external_ip=None):
    if external_ip is None:
      ip = self._last_external_ip
    else:
      ip = external_ip
    
    if ip not in self._allocated_external_ips_and_ports:
      self._allocated_external_ips_and_ports[ip] = self._nat_pool_config['external_port_low_end']
    else:
      self._allocated_external_ips_and_ports[ip] += 1
      if self._is_port_pool_depleted(ip):
        ip = self._get_incremented_ip(ip)
        self._allocated_external_ips_and_ports[ip] = self._nat_pool_config['external_port_low_end']
        self._last_external_ip = ip
    
    return ip, self._allocated_external_ips_and_ports[ip]
  
  def _is_port_pool_depleted(self, external_ip):
    return (self._allocated_external_ips_and_ports[external_ip] >
            self._nat_pool_config['external_port_high_end'])
  
  def _allocate_ip(self):
    return self._last_external_ip
  
  def _get_incremented_ip(self, ip):
    return str(netaddr.IPAddress(ip) + 1)
  
  def _add_entry(self, nat_table_entry):
    key = self._get_key(nat_table_entry.internal_ip, nat_table_entry.internal_port)
    
    if key not in self._table:
      self._table[key] = nat_table_entry
      
      key_external = self._get_key(nat_table_entry.external_ip, nat_table_entry.external_port)
      self._table_external[key_external] = nat_table_entry
    else:
      raise ValueError("cannot add a NAT table entry: entry already exists")
  
  def _get_key(self, internal_ip, internal_port):
    return str(internal_ip) + str(internal_port)


class NatTableEntry(object):
  
  def __init__(self, address_family, protocol, internal_ip, internal_port,
               external_ip, external_port, lifetime):
    self._address_family = address_family
    self._protocol = protocol
    self._internal_ip = internal_ip
    self._internal_port = internal_port
    self._external_ip = external_ip
    self._external_port = external_port
    self._lifetime = lifetime
  
  @property
  def address_family(self):
    return self._address_family
  
  @property
  def protocol(self):
    return self._protocol
  
  @property
  def internal_ip(self):
    return self._internal_ip
  
  @property
  def internal_port(self):
    return self._internal_port
  
  @property
  def external_ip(self):
    return self._external_ip
  
  @property
  def external_port(self):
    return self._external_port
  
  @property
  def lifetime(self):
    return self._lifetime
  
  def __str__(self):
    return str(self.to_dict())
  
  def to_dict(self):
    return {
      'address_family': self.address_family,
      'protocol': self.protocol,
      'internal_ip': self.internal_ip,
      'internal_port': self.internal_port,
      'external_ip': self.external_ip,
      'external_port': self.external_port,
      'lifetime': self.lifetime,
    }
