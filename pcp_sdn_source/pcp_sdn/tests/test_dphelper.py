import unittest

from .. import dphelper

#===============================================================================

class TestFlowTableHelper(unittest.TestCase):
  
  def setUp(self):
    self.table_names = [ 
      'pcp_message_forwarding',
      'nat_port_match',
      'nat_internal_to_external',
      'nat_external_to_internal',
      'packet_forwarding'
    ]
    
    self.last_table_id = len(self.table_names) - 1
    
    self.table_helper = dphelper.FlowTableHelper(self.table_names)
  
  def test_getitem(self):
    self.assertEqual(self.table_helper['nat_internal_to_external'], 2)
  
  def test_getitem_invalid_name(self):
    with self.assertRaises(KeyError):
      self.table_helper['invalid_table_name']
  
  def test_set_existing_entry_alias(self):
    self.table_helper['arp_forwarding'] = 0
    
    self.assertEqual(self.table_helper['arp_forwarding'], 0)
    self.assertEqual(self.table_helper['pcp_message_forwarding'], 0)  
  
  def test_set_existing_entry_different_table_id(self):
    self.table_helper['pcp_message_forwarding'] = 2
    
    self.assertEqual(self.table_helper['pcp_message_forwarding'], 2)  
    self.assertEqual(self.table_helper['nat_internal_to_external'], 2)  
  
  def test_next_table_id_by_name(self):
    self.assertEqual(self.table_helper.next_table_id('nat_internal_to_external'), 3)
  
  def test_next_table_id_by_id(self):
    self.assertEqual(self.table_helper.next_table_id(1), 2)
  
  def test_next_table_id_invalid_table_id(self):
    with self.assertRaises(ValueError):
      self.table_helper.next_table_id(-1)
  
  def test_next_table_id_last_table(self):
    with self.assertRaises(ValueError):
      self.table_helper.next_table_id(self.last_table_id)
    
    with self.assertRaises(ValueError):
      self.table_helper.next_table_id(self.table_names[-1])
  