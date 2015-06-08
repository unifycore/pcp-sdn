"""
This module represents the PCP server.

The behavior of the PCP server aims to follow the RFC 6887 specification.
"""

#===============================================================================

import time

from ryu.lib import packet

from .. import dphelper
from . import pcpmessage
from ..nat import nathandler

from ..app_config import app_config

import logging

#===============================================================================


class PcpServer(object):
  
  def __init__(self):
    self._start_time = time.time()
  
  # FIXME: For the time being, a physical switch port must be explicitly specified
  # as the output port. `ofdatapath` crashes when OFPP_TABLE is used as the output port.
  def process_pcp_request(self, forwarder, pcp_request_packet, pcp_response_out_port, nat_handler):
    pcp_request_ipv4 = pcp_request_packet.get_protocol(packet.ipv4.ipv4)
    pcp_request = pcpmessage.PcpMessage.parse(pcp_request_packet[-1], pcp_request_ipv4.src)
    
    if pcp_request is None:
      # Drop message silently
      return
    
    if pcp_request.parse_result != pcpmessage.PcpResultCodes.SUCCESS:
      # FIXME: Return a message with result code. Serialization must be updated
      # to avoid serializing incomplete opcode-specific fields.
      logging.info("Failed to parse PCP request; PCP client IP: "
                   "{0}; result code: {1}".format(pcp_request_ipv4.src, pcp_request.parse_result))
      return
    
    mapping_params = {
      'internal_ip': pcp_request['pcp_client_ip'],
      'internal_port': pcp_request['internal_port'],
      'external_ip': pcp_request['external_ip'],
      'external_port': pcp_request['external_port'],
      'protocol': pcp_request['protocol'],
      'lifetime': pcp_request['lifetime']
    }
    
    mapping = None
    if mapping_params['lifetime'] != 0:
      mapping_params['lifetime'] = self._get_minimum_acceptable_mapping_lifetime(
        pcp_request['opcode'], mapping_params['lifetime'])
      
      if nat_handler.find_mapping(mapping_params['internal_ip'], mapping_params['internal_port']):
        # Update the lifetime according to RFC 6887.
        mapping = nat_handler.update_mapping_lifetime(mapping_params['internal_ip'],
          mapping_params['internal_port'], mapping_params['lifetime'])
      else:
        mapping = nat_handler.create_mapping(**mapping_params)
    else:
      nat_handler.remove_mapping(mapping_params['internal_ip'], mapping_params['internal_port'],
        mapping_removal_type=nathandler.MappingRemovalType.REQUESTED_BY_CLIENT)
    
    pcp_response_packet = self._build_pcp_response_packet(pcp_request_packet, pcp_request, mapping)
    
    dphelper.send_packet(forwarder, pcp_response_packet, out_port=pcp_response_out_port)
  
  def _get_minimum_acceptable_mapping_lifetime(self, opcode, lifetime):
    """
    Return the minimum acceptable mapping lifetime given the PCP opcode. If
    `lifetime` is below the required minimum value for PCP MAP or PCP PEER
    mappings, return the corresponding minimum lifetime.
    """
    
    if (opcode == pcpmessage.PcpMessageOpcodes.MAP and
        lifetime < app_config['default_pcp_map_assigned_lifetime_seconds']):
      return app_config['default_pcp_map_assigned_lifetime_seconds']
    elif (opcode == pcpmessage.PcpMessageOpcodes.PEER and
          lifetime < app_config['default_pcp_peer_assigned_lifetime_seconds']):
      return app_config['default_pcp_peer_assigned_lifetime_seconds']
    else:
      return lifetime
  
  def _build_pcp_response_packet(self, pcp_request_packet, pcp_request, mapping):
    pcp_request_ethernet = pcp_request_packet.get_protocol(packet.ethernet.ethernet)
    pcp_request_ipv4 = pcp_request_packet.get_protocol(packet.ipv4.ipv4)
    pcp_request_udp = pcp_request_packet.get_protocol(packet.udp.udp)
    
    pcp_response_packet = packet.packet.Packet()
    pcp_response_packet.add_protocol(packet.ethernet.ethernet(ethertype=pcp_request_ethernet.ethertype,
      src=pcp_request_ethernet.dst, dst=pcp_request_ethernet.src))
    pcp_response_packet.add_protocol(packet.ipv4.ipv4(proto=pcp_request_ipv4.proto,
      src=pcp_request_ipv4.dst, dst=pcp_request_ipv4.src))
    pcp_response_packet.add_protocol(packet.udp.udp(
      src_port=pcp_request_udp.dst_port, dst_port=pcp_request_udp.src_port))
    
    pcp_response = self._build_pcp_response_payload(pcp_request, mapping)
    
    pcp_response_packet.add_protocol(pcp_response.serialize())
    
    return pcp_response_packet
  
  def _build_pcp_response_payload(self, pcp_request, mapping=None,
                                  result=pcpmessage.PcpResultCodes.SUCCESS):
    """
    Build PCP response payload.
    
    If `mapping` is not None, lifetime, external IP address and external port
    are assigned to the payload. Otherwise, 0 lifetime is assigned and external
    IP address and port are left intact.
    """
    
    pcp_response = pcpmessage.PcpMessage(**dict(pcp_request.items()))
    pcp_response.update({
      'version': 2,
      'message_type': pcpmessage.PcpMessageTypes.RESPONSE,
      'result_code': result,
      'epoch_time': self._calculate_epoch_time()
    })
    
    if mapping is not None:
      pcp_response['lifetime'] = mapping['lifetime']
      
      if pcp_request['opcode'] in [pcpmessage.PcpMessageOpcodes.MAP, pcpmessage.PcpMessageOpcodes.PEER]:
        pcp_response.update({
          'external_ip': mapping['external_ip'],
          'external_port': mapping['external_port'],
        })
    else:
      pcp_response['lifetime'] = 0
    
    return pcp_response
  
  def _calculate_epoch_time(self):
    return int(round(time.time() - self._start_time))
  