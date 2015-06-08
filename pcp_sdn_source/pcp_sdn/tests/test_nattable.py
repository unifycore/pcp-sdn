import unittest

from ..nat import nattable

#===============================================================================


class TestNatTable(unittest.TestCase):
  
  _NAT_POOL_CONFIG = {
    "internal_ip_low_end": "172.16.0.1",
    "internal_ip_high_end": "172.16.255.254",
    "internal_port_low_end": 1,
    "internal_port_high_end": 65535,
    "external_ip_low_end": "200.0.0.1",
    "external_ip_high_end": "200.0.255.254",
    "external_port_low_end": 49152,
    "external_port_high_end": 65535,
    "ip_allocation_type": nattable.NatTableAllocationType.ROUND_ROBIN,
    "port_allocation_type": nattable.NatTableAllocationType.ROUND_ROBIN
  }
  
  def setUp(self):
    self.table = nattable.NatTable(**self._NAT_POOL_CONFIG)
    self.table_entry_args_explicit = {
      'internal_ip': "172.16.1.1",
      'internal_port': 2000,
      'lifetime': 3600,
      'external_ip': "200.0.0.1",
      'external_port': 50000,
      'protocol': nattable.IpUpperProtocol.TCP
    }
    self.table_entry_args = {
      'internal_ip': "172.16.1.1",
      'internal_port': 2000,
      'lifetime': 3600,
    }
  
  def test_add_entry_explicit_args(self):
    self.table.add_entry(**self.table_entry_args_explicit)
    
    table_entry = self.table.find_entry("172.16.1.1", 2000)
    
    for entry_param_name, entry_param_value in self.table_entry_args_explicit.items():
      self.assertEqual(getattr(table_entry, entry_param_name), entry_param_value)
  
  def test_add_entry_already_existing_internal_ip_and_port(self):
    self.table.add_entry(**self.table_entry_args)
    with self.assertRaises(ValueError):
      self.table.add_entry(**self.table_entry_args)
  
  def test_add_entry_next_port_round_robin(self):
    self.table.add_entry(**self.table_entry_args)
    
    self.table_entry_args['internal_port'] = 2001
    self.table.add_entry(**self.table_entry_args)
    
    table_entry = self.table.find_entry("172.16.1.1", 2001)
    self.assertEqual(table_entry.external_ip, "200.0.0.1")
    self.assertEqual(table_entry.external_port, 49153)
  
  def test_add_entry_next_ip_round_robin(self):
    pool_config = dict(self._NAT_POOL_CONFIG)
    pool_config['external_port_high_end'] = pool_config['external_port_low_end']
    self.table = nattable.NatTable(**pool_config)
    
    self.table.add_entry(**self.table_entry_args)
    
    self.table_entry_args['internal_port'] = 2001
    self.table.add_entry(**self.table_entry_args)
    
    table_entry = self.table.find_entry("172.16.1.1", 2001)
    self.assertEqual(table_entry.external_ip, "200.0.0.2")
    self.assertEqual(table_entry.external_port, 49152)
  
  def test_update_entry_lifetime(self):
    self.table.add_entry(**self.table_entry_args)
    
    self.table.update_entry_lifetime(self.table_entry_args['internal_ip'],
                                     self.table_entry_args['internal_port'],
                                     400)
    table_entry = self.table.find_entry(self.table_entry_args['internal_ip'],
                                        self.table_entry_args['internal_port'])
    self.assertEqual(table_entry.lifetime, 400)
  
  def test_remove_entry(self):
    self.table.add_entry(**self.table_entry_args)
    self.table.remove_entry(
      self.table_entry_args['internal_ip'], self.table_entry_args['internal_port'])
    
    self.assertEqual(self.table.find_entry(
      self.table_entry_args['internal_ip'], self.table_entry_args['internal_port']), None)
  