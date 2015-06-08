"""
This module defines data and constants used by the modules in the `pcp` package.
"""

#===============================================================================

from ryu.ofproto import ether
from ryu.ofproto import inet

from ..app_config import app_config

#===============================================================================

SUPPORTED_PCP_VERSIONS = [2]

PCP_REQUEST_FIELDS = {
  'eth_type': ether.ETH_TYPE_IP,
  'ip_proto': inet.IPPROTO_UDP,
  'udp_dst': app_config['pcp_server_listening_port']
}

PCP_RESPONSE_FIELDS = {
  'eth_type': ether.ETH_TYPE_IP,
  'ip_proto': inet.IPPROTO_UDP,
  'udp_src': app_config['pcp_server_listening_port']
}

PCP_RESPONSE_MULTICAST_FIELDS = {
  'eth_type': ether.ETH_TYPE_IP,
  'ipv4_dst': "224.0.0.1",       # All Hosts multicast group address
  'ip_proto': inet.IPPROTO_UDP,
  'udp_src': app_config['pcp_server_listening_port'],
  'udp_dst': app_config['pcp_client_multicast_port']
}
