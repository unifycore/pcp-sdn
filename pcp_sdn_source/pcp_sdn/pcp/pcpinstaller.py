"""
This module installs flow entries that forward PCP messages between PCP clients
and the PCP server.
"""

#===============================================================================

from .. import dphelper

from . import pcp_data

#===============================================================================


def install_pcp_message_forwarding(forwarder, port, table_id, next_table_id,
                                   priority=0):
  """
  Install the following flow entries:
  
  * forward PCP request from the specified port to the controller
  * forward PCP response from the controller out the specified port
  
  `table_id` is the table ID to install the flow entries to.
  
  `next_table_id` is the table ID where packets should be forwarded to if they
  don't match the flow entries in `table_id`. 
  """
  
  _install_pcp_request_forwarding(forwarder, port, table_id, priority)
  _install_pcp_response_forwarding(forwarder, port, table_id, priority)
  
  dphelper.add_instruction_goto_next_table(forwarder, table_id, next_table_id)


def _install_pcp_request_forwarding(forwarder, pcp_request_in_port, table_id, priority):
  ofproto = forwarder.ofproto
  parser = forwarder.ofproto_parser
  
  match = parser.OFPMatch(in_port=pcp_request_in_port, **pcp_data.PCP_REQUEST_FIELDS)
  actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
  dphelper.add_flow_entry(forwarder, match, actions, table_id=table_id,
                          priority=priority)


def _install_pcp_response_forwarding(forwarder, pcp_response_out_port, table_id, priority):
  ofproto = forwarder.ofproto
  parser = forwarder.ofproto_parser
  
  match = parser.OFPMatch(in_port=ofproto.OFPP_CONTROLLER, **pcp_data.PCP_RESPONSE_FIELDS)
  actions = [parser.OFPActionOutput(pcp_response_out_port)]
  dphelper.add_flow_entry(forwarder, match, actions, table_id=table_id,
                          priority=priority)

