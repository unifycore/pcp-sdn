"""
This module is the entry point of the "PCP over SDN" network application.
"""

#===============================================================================

from ryu.base import app_manager
from ryu.lib import packet
from ryu.controller import ofp_event
from ryu.controller import handler

from pcp_sdn import app_config

app_config.init()

from pcp_sdn import dphelper
from pcp_sdn import arphandler

from pcp_sdn.pcp import pcpinstaller
from pcp_sdn.pcp import pcpserver
from pcp_sdn.pcp import pcpmessage

from pcp_sdn.nat import nathandler
from pcp_sdn.nat import natinstaller

#===============================================================================


class PcpSdnApp(app_manager.RyuApp):
  
  # FIXME: These constants are temporary. They should be specified when invoking
  # the application.
  _PORTS = {
    'access': 1,
    'external': 2
  }
  
  _FLOW_TABLES = [
    'pcp_message_forwarding',
    'nat_port_match',
    'nat_internal_to_external',
    'nat_external_to_internal',
    'packet_forwarding',
  ]
  
  _ARP_FORWARDING_PRIORITY = 2
  _PCP_FORWARDING_PRIORITY = 3
  
  def __init__(self, *args, **kwargs):
    super(PcpSdnApp, self).__init__(*args, **kwargs)
    
    self.flow_tables = dphelper.FlowTableHelper(self._FLOW_TABLES)
    # Use the same flow table for multiple purposes.
    self.flow_tables['arp_forwarding'] = self.flow_tables['pcp_message_forwarding']
    self.flow_tables['mac_overwriting'] = self.flow_tables['pcp_message_forwarding']
    
    self.pcp_server = pcpserver.PcpServer()
    
    self.nat_handler = None
    self.arp_handler = None
    
    self._datapath_mac_addrs = set([])
  
  @handler.set_ev_cls(ofp_event.EventOFPSwitchFeatures, handler.CONFIG_DISPATCHER)
  def switch_features_handler(self, ev):
    datapath = ev.msg.datapath
    
    self._datapath_mac_addrs.add(dphelper.get_mac_addr_from_datapath(datapath))
    
    dphelper.clear_datapath(datapath)
    
    self._install_arp_forwarding(datapath,
      in_ports=[self._PORTS['access'], self._PORTS['external']],
      table_id=self.flow_tables['arp_forwarding'])
    
    pcpinstaller.install_pcp_message_forwarding(datapath, self._PORTS['access'],
      self.flow_tables['pcp_message_forwarding'], self.flow_tables['nat_port_match'],
      priority=self._PCP_FORWARDING_PRIORITY)
    
    self.nat_handler = nathandler.NatHandler(datapath, self._PORTS['external'],
      [self.flow_tables['nat_port_match'], self.flow_tables['nat_internal_to_external'],
       self.flow_tables['nat_external_to_internal']],
      self.flow_tables['packet_forwarding'])
    
    self.arp_handler = arphandler.ArpHandler(self.flow_tables['mac_overwriting'],
                                             self.flow_tables['nat_port_match'])
    
    self._install_simple_packet_forwarding(datapath, table_id=self.flow_tables['packet_forwarding'])
  
  @handler.set_ev_cls(ofp_event.EventOFPPacketIn, handler.MAIN_DISPATCHER)
  def packet_in_handler(self, ev):
    packet_ = packet.packet.Packet(ev.msg.data)
    
    if pcpmessage.is_pcp(packet_):
      self.pcp_server.process_pcp_request(ev.msg.datapath, packet_, self._PORTS['access'], self.nat_handler)
    
    if arphandler.is_arp(packet_):
      # FIXME: This limits ARP processing to two ports on one forwarder.
      in_port = ev.msg.match['in_port']
      if in_port == self._PORTS['access']:
        out_port = self._PORTS['external']
      else:
        out_port = self._PORTS['access']
      
      self.arp_handler.process_arp(ev.msg.datapath, packet_, in_port, out_port)
  
  @handler.set_ev_cls(ofp_event.EventOFPFlowRemoved, handler.MAIN_DISPATCHER)
  def flow_entry_removed_handler(self, ev):
    msg = ev.msg
    ofproto = msg.datapath.ofproto
    match = ev.msg.match
    
    if msg.reason == ofproto.OFPRR_IDLE_TIMEOUT:
      if msg.table_id == self.flow_tables['nat_internal_to_external']:
        ip_src_name = natinstaller.MATCH_FIELD_NAME_MAPS['ip_src'][match['eth_type']]
        port_src_name = natinstaller.MATCH_FIELD_NAME_MAPS['port_src'][match['ip_proto']]
        
        self.nat_handler.remove_mapping(match[ip_src_name], match[port_src_name],
          nathandler.MappingRemovalType.FLOW_ENTRY_REMOVED_BY_FORWARDER)
        
        self.logger.info("Flow entry expired, removed mapping entry: {0}".format(match))
      elif msg.table_id == self.flow_tables['nat_external_to_internal']:
        # FIXME: Make it possible to remove mapping entries by specifying the
        # external IP and port. For now, only the flow entry from the internal-
        # -to-external table causes the mapping entry to be removed.
        pass
      else:
        pass
  
  def _install_simple_packet_forwarding(self, forwarder, table_id=0):
    """
    Install a table performing simple packet forwarding between the access
    network and the external network, based on physical ports.
    """
    
    parser = forwarder.ofproto_parser
    
    match = parser.OFPMatch(in_port=self._PORTS['access'])
    actions = [parser.OFPActionOutput(port=self._PORTS['external'])]
    dphelper.add_flow_entry(forwarder, match, actions, table_id=table_id)
    
    match = parser.OFPMatch(in_port=self._PORTS['external'])
    actions = [parser.OFPActionOutput(port=self._PORTS['access'])]
    dphelper.add_flow_entry(forwarder, match, actions, table_id=table_id)
  
  def _install_arp_forwarding(self, forwarder, in_ports, table_id):
    """
    Install a flow entries performing forwarding of ARP messages to the
    controller on the specified ports of the specified forwarder.
    """
    
    parser = forwarder.ofproto_parser
    ofproto = forwarder.ofproto
    
    for in_port in in_ports:
      match = parser.OFPMatch(in_port=in_port, eth_type=0x806)
      actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
      dphelper.add_flow_entry(forwarder, match, actions, table_id=table_id,
                              priority=self._ARP_FORWARDING_PRIORITY)
      