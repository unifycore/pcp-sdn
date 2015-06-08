"""
This module installs flow tables and flow table entries to the NAT forwarder.
"""

#===============================================================================

from .. import dphelper
from . import nattable

from ..app_config import app_config

#===============================================================================

# Generic mappings for flow entry match fields for IP addresses and ports
MATCH_FIELD_NAME_MAPS = {
  'ip_src': {
    nattable.AddressFamily.IPv4: 'ipv4_src',
    nattable.AddressFamily.IPv6: 'ipv6_src',
  },
  
  'ip_dst': {
    nattable.AddressFamily.IPv4: 'ipv4_dst',
    nattable.AddressFamily.IPv6: 'ipv6_dst',
  },
  
  'port_src': {
    nattable.IpUpperProtocol.TCP: 'tcp_src',
    nattable.IpUpperProtocol.UDP: 'udp_src',
  },
  
  'port_dst': {
    nattable.IpUpperProtocol.TCP: 'tcp_dst',
    nattable.IpUpperProtocol.UDP: 'udp_dst',
  },
}

#===============================================================================


class NatInstaller(object):
  
  """
  This class:
  
  * installs NAT flow tables into the specified forwarder
  * installs NAT flow entries
  * uninstalls NAT flow entries
  * updates lifetime of existing NAT flow entries
  """
  
  _TRANSLATION_DIRECTIONS = (_INTERNAL_TO_EXTERNAL, _EXTERNAL_TO_INTERNAL) = (0, 1)
  
  def __init__(self, forwarder, external_port, table_ids, next_table_id):
    """
    Install NAT tables on the specified forwarder.
    
    Packets with translated addresses and ports are sent out `external_port`.
    
    `table_ids` is a list containing the following flow table IDs:
    
      [port matching, internal -> external translation, external -> internal translation].
    
    `next_table_id` is the table ID where packets should be forwarded to if they
    don't match the flow entries in tables specified in `table_ids`. 
    """
    
    self._forwarder = forwarder
    self._external_port = external_port
    
    self._table_ids = {
      'nat_port_match': table_ids[0],
      'nat_internal_to_external': table_ids[1],
      'nat_external_to_internal': table_ids[2],
    }
    self._next_table_id = next_table_id
    
    self._install_table_port_matching()
  
  def install_nat_entry(self, nat_table_entry, priority=app_config['default_nat_flow_entry_priority']):
    """
    Install new flow entries to the NAT forwarder matching the NAT table entry.
    
    `priority` defines the flow entry priority. Make sure the priority is higher
    than the no-match entry, otherwise the no-match entry may be preferred. The
    default priority value ensures that the NAT flow entries will be preferred.
    """
    
    self._install_nat_entry(self._table_ids['nat_internal_to_external'],
      nat_table_entry, self._INTERNAL_TO_EXTERNAL, priority)
    self._install_nat_entry(self._table_ids['nat_external_to_internal'],
      nat_table_entry, self._EXTERNAL_TO_INTERNAL, priority)
  
  def uninstall_nat_entry(self, nat_table_entry, priority=app_config['default_nat_flow_entry_priority']):
    """
    Uninstall flow entries from the NAT forwarder matching the NAT table entry.
    """
    
    self._uninstall_nat_entry(self._table_ids['nat_internal_to_external'],
      nat_table_entry, self._INTERNAL_TO_EXTERNAL, priority)
    self._uninstall_nat_entry(self._table_ids['nat_external_to_internal'],
      nat_table_entry, self._EXTERNAL_TO_INTERNAL, priority)
  
  def modify_nat_entry_lifetime(self, nat_table_entry, priority=app_config['default_nat_flow_entry_priority']):
    """
    Modify the lifetime of existing NAT flow entries matching the NAT table entry.
    
    Implementation note:
    
    To update the lifetime on the flow entries, `idle_timeout` has to be
    modified. According to the OpenFlow switch specification 1.3,
    `OFPFC_MODIFY` does not modify `idle_timeout`. To work around this, the flow
    entries are simply removed and added back (with the modified timeout value)
    so that the modification of `idle_timeout` takes effect.
    """
    
    self.uninstall_nat_entry(nat_table_entry, priority)
    self.install_nat_entry(nat_table_entry, priority)
  
  def _install_nat_entry(self, table_id, nat_table_entry, translation_direction, priority):
    match_data = self._get_match_data(nat_table_entry, translation_direction)
    action_set_data = self._get_action_set_data(nat_table_entry, translation_direction)
    self._install_nat_table_entry(table_id, match_data, action_set_data,
                                  nat_table_entry.lifetime, priority)
  
  def _uninstall_nat_entry(self, table_id, nat_table_entry, translation_direction, priority):
    match_data = self._get_match_data(nat_table_entry, translation_direction)
    self._uninstall_nat_table_entry(table_id, match_data, priority)
  
  def _get_match_data(self, nat_table_entry, translation_direction):
    if translation_direction == self._INTERNAL_TO_EXTERNAL:
      field_name_direction_suffix = 'src'
      nat_table_entry_attr_name_prefix = 'internal'
    elif translation_direction == self._EXTERNAL_TO_INTERNAL:
      field_name_direction_suffix = 'dst'
      nat_table_entry_attr_name_prefix = 'external'
    else:
      raise ValueError("invalid translation direction: {0}".format(translation_direction))
    
    ip_field_name = MATCH_FIELD_NAME_MAPS['ip_' + field_name_direction_suffix][nat_table_entry.address_family]
    port_field_name = MATCH_FIELD_NAME_MAPS['port_' + field_name_direction_suffix][nat_table_entry.protocol]
    
    match_data = {
      'eth_type': nat_table_entry.address_family,
      'ip_proto': nat_table_entry.protocol,
      ip_field_name: getattr(nat_table_entry, nat_table_entry_attr_name_prefix + '_ip'),
      port_field_name: getattr(nat_table_entry, nat_table_entry_attr_name_prefix + '_port')
    }
    
    return match_data
  
  def _get_action_set_data(self, nat_table_entry, translation_direction):
    # `nat_table_entry_attr_name_prefix` is intentionally switched since action
    # fields set the IP addresses and ports to the opposite direction (e.g.
    # source internal IP address is set to external).
    if translation_direction == self._INTERNAL_TO_EXTERNAL:
      field_name_direction_suffix = 'src'
      nat_table_entry_attr_name_prefix = 'external'
    elif translation_direction == self._EXTERNAL_TO_INTERNAL:
      field_name_direction_suffix = 'dst'
      nat_table_entry_attr_name_prefix = 'internal'
    else:
      raise ValueError("invalid translation direction: {0}".format(translation_direction))
    
    ip_field_name = MATCH_FIELD_NAME_MAPS['ip_' + field_name_direction_suffix][nat_table_entry.address_family]
    port_field_name = MATCH_FIELD_NAME_MAPS['port_' + field_name_direction_suffix][nat_table_entry.protocol]
    
    action_set_data = {
      ip_field_name: getattr(nat_table_entry, nat_table_entry_attr_name_prefix + '_ip'),
      port_field_name: getattr(nat_table_entry, nat_table_entry_attr_name_prefix + '_port')
    }
    
    return action_set_data
  
  def _install_nat_table_entry(self, table_id, match_data, action_set_field_data,
                               lifetime, priority):
    """
    Install the NAT table entry.
    
    Once the flow entry expires (defined by `lifetime`), the controller is
    notified of the removal (using the `OFPFF_SEND_FLOW_REM` flag when
    installing the flow entry).
    """
    
    ofproto = self._forwarder.ofproto
    parser = self._forwarder.ofproto_parser
    
    match = parser.OFPMatch(**match_data)
    actions = [parser.OFPActionSetField(**{field_name: field_value})
               for field_name, field_value in action_set_field_data.items()]
    instructions = [
      parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions),
      parser.OFPInstructionGotoTable(self._next_table_id)
    ]
    dphelper.add_flow_entry(
      self._forwarder, match, actions, instructions=instructions,
      table_id=table_id, idle_timeout=lifetime, priority=priority,
      flags=ofproto.OFPFF_SEND_FLOW_REM)
  
  def _uninstall_nat_table_entry(self, table_id, match_data, priority):
    parser = self._forwarder.ofproto_parser
    match = parser.OFPMatch(**match_data)
    
    dphelper.remove_flow_entry(self._forwarder, match, table_id=table_id,
                               priority=priority)
  
  def _install_table_port_matching(self):
    parser = self._forwarder.ofproto_parser
    
    match = parser.OFPMatch(in_port=self._external_port)
    dphelper.add_instruction_goto_next_table(self._forwarder,
      self._table_ids['nat_port_match'], self._table_ids['nat_external_to_internal'], match=match)
    
    dphelper.add_instruction_goto_next_table(self._forwarder,
      self._table_ids['nat_port_match'], self._table_ids['nat_internal_to_external'])
