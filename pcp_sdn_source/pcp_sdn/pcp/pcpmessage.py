"""
This module implements the PCP message format as per the RFC 6887 specification.

This module contains the following components:
* PCP message parser and serializer
* function to determine whether the received packet is a PCP message
"""

#===============================================================================

import struct
import netaddr

from ryu.lib import packet
 
from . import pcp_data
from .. import message

from ..app_config import app_config

#===============================================================================

 
def packed_str_to_int(packed_str):
  int_bytes = struct.unpack("{0}B".format(len(packed_str)), packed_str)
  
  int_to_return = 0
  for byte_ in int_bytes:
    int_to_return <<= 8
    int_to_return += byte_
  
  return int_to_return
 
 
def ip_addr_to_packed_str(ip_addr_string):
  """
  Transform an IP address in human-readable format to an IPv6 address as a
  packed string.
  
  IPv4 addresses are treated as IPv4-mapped IPv6 addresses.
  """
  
  try:
    ip_addr = netaddr.IPAddress(ip_addr_string, version=6)
  except netaddr.AddrFormatError:
    ip_addr = netaddr.IPAddress(ip_addr_string, version=4)
    ip_addr = ip_addr.ipv6()
  
  return ip_addr.packed
 
 
def packed_str_to_ip_addr(ip_addr_packed):
  """
  Transform a packed string into an IP address in human-readable format.
  
  The packed string is assumed to contain an IPc6 address. To pass an IPv4
  address, pass it as an IPv4-mapped IPv6 address.
  """
  
  ip_addr = netaddr.IPAddress(packed_str_to_int(ip_addr_packed), version=6)
  
  if ip_addr.is_ipv4_mapped():
    ip_addr = ip_addr.ipv4()
  
  return str(ip_addr)
 
 
#===============================================================================
  
  
def is_pcp(packet_):
  """
  Return True if the packet is a PCP message, False otherwise.
  """
  
  header_udp = packet_.get_protocol(packet.udp.udp)
  
  if header_udp is not None and header_udp.dst_port == app_config['pcp_server_listening_port']:
    return True
  else:
    return False
  
  
#===============================================================================
  
  
class PcpMessageTypes(object):
  TYPES = REQUEST, RESPONSE = (0, 1)
  
  
class PcpMessageOpcodes(object):
  OPCODES = ANNOUNCE, MAP, PEER = (0, 1, 2)
  
  
class PcpResultCodes(object):
  RESULT_CODES = (
    SUCCESS,
    UNSUPP_VERSION,
    NOT_AUTHORIZED,
    MALFORMED_REQUEST,
    UNSUPP_OPCODE,
    UNSUPP_OPTION,
    MALFORMED_OPTION,
    NETWORK_FAILURE,
    NO_RESOURCES,
    UNSUPP_PROTOCOL,
    USER_EX_QUOTA,
    CANNOT_PROVIDE_EXTERNAL,
    ADDRESS_MISMATCH,
    EXCESSIVE_REMOTE_PEERS
  ) = tuple(range(14))
  
 
#===============================================================================
 
 
class PcpMessage(message.Message):
  
  """
  This class:
  * parses a PCP message
  * stores the parsed data in fields
  * serializes the PCP message from fields
  
  ===================== ======================================== ===============
  Attribute             Description                              Message type
  ===================== ======================================== ===============
  version               PCP version (must always be 2)           all
  message_type          Message type - Request or Response       all
  opcode                Message opcode (MAP, PEER, ...)          all
  lifetime              Requested/Assigned lifetime              all
  pcp_client_ip         PCP client's IP address                  Request
  result_code           Result code                              Response
  epoch_time            Epoch time                               Response
  pcp_client_ip_part    Last 96 bits of PCP client's IP address  Response
  mapping_nonce         Mapping nonce                            MAP, PEER
  protocol              Upper layer protocol (TCP, ICMP, ...)    MAP, PEER
  internal_port         Internal port                            MAP, PEER
  external_port         Suggested/Assigned external port         MAP, PEER
  external_ip           Suggested/Assigned external IP address   MAP, PEER
  remote_peer_port      Remote peer port                         PEER
  remote_peer_ip        Remote peer IP address                   PEER
  ===================== ======================================== ===============
  
  For more information about PCP message format and fields, consult RFC 6887.
  """
  
  _COMMON_LENGTH = 24
  _MAP_OPCODE_LENGTH = 36
  _PEER_OPCODE_LENGTH = 56
  
  _MINIMUM_MESSAGE_LENGTH = 2
  _MAXIMUM_MESSAGE_LENGTH = 1100
  
  def __init__(self, **fields):
    super(PcpMessage, self).__init__()
    
    self._fields = fields
    self._serialized = ""
    # PCP client's IP address from the IP header
    self._pcp_client_ip_address = ""
    
    self._parse_result = PcpResultCodes.SUCCESS
    self._should_discard = False
  
  @classmethod
  def parse(cls, data, pcp_client_ip_address):
    """
    Parse the PCP message from the specified payload data.
    
    `pcp_client_ip_address` is the PCP client's IP address from the IP header
    (which must be the same as the IP address specified in the payload).
    
    On success, return the parsed message as a PcpMessage object and set the
    `parse_result` attribute to `PcpResultCodes.SUCCESS`.
    
    On failure (due to invalid data):
    
      * If the message type is not a request, the data length is less than 2
        bytes, or the version is not supported and the data length is less than
        24 bytes, return None. `None` indicates that the server should drop the
        message silently, without sending a response back to the client.
      
      * Otherwise, return a PcpMessage object and set the `parse_result`
        attribute to a value other than `PcpResultCodes.SUCCESS` (depending on
        the type of the error).
    """
    
    pcp_message = PcpMessage()
    pcp_message._pcp_client_ip_address = pcp_client_ip_address
    
    if len(data) < cls._MINIMUM_MESSAGE_LENGTH:
      return None
    
    message_type = ord(data[1]) >> 7
    
    if message_type != PcpMessageTypes.REQUEST:
      return None
    
    cls._parse_request(data, pcp_message)
    
    if pcp_message._should_discard:
      return None
    
    if len(data) % 4 != 0:
      pcp_message._parse_result = PcpResultCodes.MALFORMED_REQUEST
    if len(data) > cls._MAXIMUM_MESSAGE_LENGTH:
      pcp_message._parse_result = PcpResultCodes.MALFORMED_REQUEST
    
    return pcp_message
  
  @property
  def parse_result(self):
    return self._parse_result
  
  def serialize(self):
    """
    Serialize the PCP message, ready to be inserted into a packet.
    
    All required fields must be present, and all fields must have valid values.
    
    Raises:
    
      * KeyError - missing required field(s)
      
      * MessageSerializationError - invalid field value(s)
    """
    
    if self['message_type'] == PcpMessageTypes.REQUEST:
      self._serialize_request()
    elif self['message_type'] == PcpMessageTypes.RESPONSE:
      self._serialize_response()
    else:
      raise message.MessageSerializationError(
        "invalid message type; must be one of [{0}, {1}]".format(
           PcpMessageTypes.REQUEST, PcpMessageTypes.RESPONSE))
    
    return self._serialized
  
  @classmethod
  def _parse_request(cls, data, pcp_message):
    pcp_message['version'] = ord(data[0])
    
    if pcp_message['version'] not in pcp_data.SUPPORTED_PCP_VERSIONS:
      pcp_message._parse_result = PcpResultCodes.UNSUPP_VERSION
    
    if len(data) < cls._COMMON_LENGTH:
      pcp_message._should_discard = True
      return
    
    fields = struct.unpack("!BHL", data[1:8])
    # fields[1] is `Reserved` field, which is ignored.
    pcp_message['message_type'] = fields[0] >> 7
    pcp_message['opcode'] = fields[0] & 0x7f
    pcp_message['lifetime'] = fields[2]
    pcp_message['pcp_client_ip'] = packed_str_to_ip_addr(data[8:8+16])
    
    if pcp_message['opcode'] not in PcpMessageOpcodes.OPCODES:
      pcp_message._parse_result = PcpResultCodes.UNSUPP_OPCODE
    
    if pcp_message._pcp_client_ip_address != pcp_message['pcp_client_ip']:
      pcp_message._parse_result = PcpResultCodes.ADDRESS_MISMATCH
    
    cls._parse_opcode(data[cls._COMMON_LENGTH:], pcp_message)
  
  @classmethod
  def _parse_response(cls, data, pcp_message):
    pcp_message['version'] = ord(data[0])
    
    if pcp_message['version'] not in pcp_data.SUPPORTED_PCP_VERSIONS:
      pcp_message._parse_result = PcpResultCodes.UNSUPP_VERSION
    
    if len(data) < cls._COMMON_LENGTH:
      pcp_message._should_discard = True
      return
    
    fields = struct.unpack("!BBBLL", data[1:12])
    
    # fields[1] is `Reserved` field, which is ignored.
    pcp_message['message_type'] = fields[0] >> 7
    pcp_message['opcode'] = fields[0] & 0x7f
    pcp_message['result_code'] = fields[2]
    pcp_message['lifetime'] = fields[3]
    pcp_message['epoch_time'] = fields[4]
    
    # As per RFC 6887, `Reserved` field may contain the last 96 bits of a PCP
    # client's IP address in case of an unsuccessfully parsed PCP request.
    pcp_message['pcp_client_ip_part'] = data[12:12+12]
    
    if pcp_message['opcode'] not in PcpMessageOpcodes.OPCODES:
      pcp_message._parse_result = PcpResultCodes.UNSUPP_OPCODE
    
    cls._parse_opcode(data[cls._COMMON_LENGTH:], pcp_message)
  
  @classmethod
  def _parse_opcode(cls, data, pcp_message):
    if pcp_message['opcode'] == PcpMessageOpcodes.MAP:
      cls._parse_opcode_map(data, pcp_message)
    elif pcp_message['opcode'] == PcpMessageOpcodes.PEER:
      cls._parse_opcode_peer(data, pcp_message)
  
  @classmethod
  def _parse_opcode_common(cls, data, pcp_message):
    # data[13:16] is `Reserved` field, which is ignored.
    pcp_message['mapping_nonce'] = data[:12].encode('hex')
    pcp_message['protocol'] = ord(data[12])
    (pcp_message['internal_port'],
     pcp_message['external_port']) = struct.unpack("!HH", data[16:20])
    pcp_message['external_ip'] = packed_str_to_ip_addr(data[20:36])
  
  @classmethod
  def _parse_opcode_map(cls, data, pcp_message):
    if len(data) < cls._MAP_OPCODE_LENGTH:
      pcp_message._parse_result = PcpResultCodes.MALFORMED_REQUEST
      return
    
    cls._parse_opcode_common(data, pcp_message)
    
    if (pcp_message['lifetime'] != 0 and pcp_message['protocol'] == 0 and
        pcp_message['internal_port']) != 0:
      pcp_message._parse_result = PcpResultCodes.MALFORMED_REQUEST
      return
    
    if pcp_message['internal_port'] == 0:
      pcp_message._parse_result = PcpResultCodes.UNSUPP_PROTOCOL
      return
  
  @classmethod
  def _parse_opcode_peer(cls, data, pcp_message):
    if len(data) < cls._PEER_OPCODE_LENGTH:
      pcp_message._parse_result = PcpResultCodes.MALFORMED_REQUEST
      return
    
    cls._parse_opcode_common(data, pcp_message)
    
    pcp_message['remote_peer_port'] = struct.unpack("!H", data[36:38])[0]
    pcp_message['remote_peer_ip'] = packed_str_to_ip_addr(data[40:56])
  
  def _serialize_request(self):
    message_fields = []
    message_fields.append(self['version'])
    message_fields.append(self['opcode'])
    message_fields[-1] = message_fields[-1] | (self['message_type'] << 7)
    message_fields.append(0)      # `Reserved` field, must be zero
    message_fields.append(self['lifetime'])
    
    self._serialized = struct.pack("!BBHL", *message_fields)
    self._serialized += ip_addr_to_packed_str(self['pcp_client_ip'])
    
    self._serialize_opcode()
  
  def _serialize_response(self):
    message_fields = []
    message_fields.append(self['version'])
    message_fields.append(self['opcode'])
    message_fields[-1] = message_fields[-1] | (self['message_type'] << 7)
    message_fields.append(0)      # `Reserved` field, must be zero
    message_fields.append(self['result_code'])
    message_fields.append(self['lifetime'])
    message_fields.append(self['epoch_time'])
    
    self._serialized = struct.pack("!BBBBLL", *message_fields)
    
    if self['result_code'] == PcpResultCodes.SUCCESS:
      self._serialized += '\x00' * 12
    else:
      if 'pcp_client_ip' in self:
        self._serialized += ip_addr_to_packed_str(self['pcp_client_ip'])[4:]
      else:
        self._serialized += '\x00' * 12
    
    self._serialize_opcode()
  
  def _serialize_opcode(self):
    if self['opcode'] == PcpMessageOpcodes.MAP:
      self._serialize_opcode_map()
    elif self['opcode'] == PcpMessageOpcodes.PEER:
      self._serialize_opcode_peer()
  
  def _serialize_opcode_common(self):
    self._serialized += self['mapping_nonce'].decode('hex')
    self._serialized += chr(self['protocol'])
    self._serialized += '\x00' * 3     # `Reserved` field, set to zero
    self._serialized += struct.pack(
      "!HH", self['internal_port'], self['external_port'])
    self._serialized += ip_addr_to_packed_str(self['external_ip'])
  
  def _serialize_opcode_map(self):
    self._serialize_opcode_common()
  
  def _serialize_opcode_peer(self):
    self._serialize_opcode_common()
    
    self._serialized += struct.pack("!H", self['remote_peer_port'])
    self._serialized += '\x00' * 2     # `Reserved` field, set to zero
    self._serialized += ip_addr_to_packed_str(self['remote_peer_ip'])
    