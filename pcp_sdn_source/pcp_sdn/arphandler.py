"""
This module:
* implements simple ARP processing
"""

#===============================================================================

from ryu.lib import packet

from . import dphelper

from app_config import app_config

#===============================================================================


def is_arp(packet_):
  """
  Return True if the packet is an ARP request, False otherwise.
  """
  
  header_arp = packet_.get_protocol(packet.arp.arp)
  is_header_arp = header_arp is not None
  return is_header_arp


class ArpTableEntry(object):
  
  def __init__(self, src_ip, dst_ip, src_mac, dst_mac, datapath_mac):
    self.src_ip = src_ip
    self.dst_ip = dst_ip
    self.src_mac = src_mac
    self.dst_mac = dst_mac
    self.datapath_mac = datapath_mac


class ArpHandler(object):
  
  def __init__(self, arp_flow_entries_table_id, next_table_id):
    # Key: destination IP
    # Value: `ArpTableEntry` object
    self._arp_table = {}
    self._arp_flow_entries_table_id = arp_flow_entries_table_id
    self._next_table_id = next_table_id
  
  def process_arp(self, datapath, packet_, in_port, out_port):
    header_arp = packet_.get_protocol(packet.arp.arp)
    
    if header_arp.opcode == packet.arp.ARP_REQUEST:
      self._process_arp_request(datapath, packet_, header_arp, in_port, out_port)
    elif header_arp.opcode == packet.arp.ARP_REPLY:
      self._process_arp_reply(datapath, packet_, header_arp, in_port, out_port)
  
  def _process_arp_request(self, datapath, packet_, header_arp, in_port, out_port):
    datapath_mac_addr = dphelper.get_mac_addr_from_datapath(datapath)
    
    self._arp_table[header_arp.dst_ip] = ArpTableEntry(header_arp.src_ip,
      header_arp.dst_ip, header_arp.src_mac, None, datapath_mac_addr)
    
    header_arp_reply = packet.arp.arp_ip(packet.arp.ARP_REPLY, datapath_mac_addr,
      header_arp.dst_ip, header_arp.src_mac, header_arp.src_ip)
    arp_reply = self._build_arp_message(header_arp_reply)
    dphelper.send_packet(datapath, arp_reply, in_port)
    
    # ARP reply has been sent to the source host, with the forwarder's MAC address
    # as the destination MAC. We need to determine the real destination MAC.
    
    # Send ARP request to the destination IP out the `out_port`.
    header_arp_request_to_dest = packet.arp.arp_ip(packet.arp.ARP_REQUEST,
      datapath_mac_addr, header_arp.src_ip, 'ff:ff:ff:ff:ff:ff', header_arp.dst_ip)
    arp_request_to_dest = self._build_arp_message(header_arp_request_to_dest)
    dphelper.send_packet(datapath, arp_request_to_dest, out_port)
  
  def _process_arp_reply(self, datapath, packet_, header_arp, in_port, out_port):
    if header_arp.src_ip not in self._arp_table:
      return
    
    arp_table_entry = self._arp_table[header_arp.src_ip]
    arp_table_entry.dst_mac = header_arp.src_mac
    
    datapath_mac_addr = dphelper.get_mac_addr_from_datapath(datapath)
    
    # Install flow entries that modify the forwarder's MAC address with the
    # appropriate host's MAC address. `in_port` and `out_port` are switched on
    # purpose.
    self._install_mac_modifying_flow_entries(datapath, out_port, in_port,
      arp_table_entry.src_mac, arp_table_entry.dst_mac, datapath_mac_addr)
  
  def _build_arp_message(self, header_arp):
    arp_reply = packet.packet.Packet()
    arp_reply.add_protocol(packet.ethernet.ethernet(ethertype=0x806,
      src=header_arp.src_mac, dst=header_arp.dst_mac))
    arp_reply.add_protocol(header_arp)
    
    return arp_reply
  
  def _install_mac_modifying_flow_entries(self, datapath, in_port, out_port,
    in_mac, out_mac, datapath_mac):
    
    ofproto = datapath.ofproto
    parser = datapath.ofproto_parser
    
    match = parser.OFPMatch(in_port=in_port, eth_src=in_mac, eth_dst=datapath_mac)
    actions = [parser.OFPActionSetField(eth_src=datapath_mac),
               parser.OFPActionSetField(eth_dst=out_mac)]
    instructions = [
      parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions),
      parser.OFPInstructionGotoTable(self._next_table_id)
    ]
    dphelper.add_flow_entry(
      datapath, match, actions, instructions=instructions,
      table_id=self._arp_flow_entries_table_id,
      priority=app_config['default_mac_modifying_flow_entries_priority'])
    
    match = parser.OFPMatch(in_port=out_port, eth_src=out_mac, eth_dst=datapath_mac)
    actions = [parser.OFPActionSetField(eth_src=datapath_mac),
               parser.OFPActionSetField(eth_dst=in_mac)]
    instructions = [
      parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions),
      parser.OFPInstructionGotoTable(self._next_table_id)
    ]
    dphelper.add_flow_entry(
      datapath, match, actions, instructions=instructions,
      table_id=self._arp_flow_entries_table_id,
      priority=app_config['default_mac_modifying_flow_entries_priority'])
    
  