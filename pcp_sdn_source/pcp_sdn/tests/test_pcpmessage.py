import unittest

from ..pcp import pcpmessage

#===============================================================================


class TestPcpMessage(unittest.TestCase):
  
  def setUp(self):
    self.pcp_client_ip = "192.168.1.1"
    
    self.pcp_fields_request_map_common = {
      'version': 2,
      'message_type': pcpmessage.PcpMessageTypes.REQUEST,
      'opcode': pcpmessage.PcpMessageOpcodes.MAP,
      'lifetime': 300,
      'pcp_client_ip': self.pcp_client_ip
    }
    
    self.pcp_fields_request_peer_common = dict(self.pcp_fields_request_map_common)
    self.pcp_fields_request_peer_common['opcode'] = pcpmessage.PcpMessageOpcodes.PEER
    
    self.pcp_fields_request_announce_common = dict(self.pcp_fields_request_map_common)
    self.pcp_fields_request_announce_common['opcode'] = pcpmessage.PcpMessageOpcodes.ANNOUNCE
    
    self.pcp_fields_response_map_common = {
      'version': 2,
      'message_type': pcpmessage.PcpMessageTypes.RESPONSE,
      'opcode': pcpmessage.PcpMessageOpcodes.MAP,
      'result_code': 1,
      'lifetime': 300,
      'epoch_time': 123461316
    }
    
    
    self.pcp_fields_map = {
      'mapping_nonce': "0102030464ff8e110a090204",
      'protocol': 0x11,
      'internal_port': 1250,
      'external_port': 5555,
      'external_ip': "200.0.0.1"
    }
    
    self.pcp_fields_peer = {
      'mapping_nonce': "0102030464ff8e110a090204",
      'protocol': 0x11,
      'internal_port': 1250,
      'external_port': 5555,
      'external_ip': "200.0.0.1",
      'remote_peer_port': 4444,
      'remote_peer_ip': "210.0.0.100"
    }
    
    
    self.pcp_data_request_map_common = (
      '\x02\x01\x00\x00'
      '\x00\x00\x01,'
      '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff\xc0\xa8\x01\x01'
    )
    
    data_list = list(self.pcp_data_request_map_common)
    message_type = ord(data_list[1]) >> 7
    data_list[1] = chr(message_type | pcpmessage.PcpMessageOpcodes.PEER)
    self.pcp_data_request_peer_common = ''.join(data_list)
    
    data_list = list(self.pcp_data_request_map_common)
    message_type = ord(data_list[1]) >> 7
    data_list[1] = chr(message_type | pcpmessage.PcpMessageOpcodes.ANNOUNCE)
    self.pcp_data_request_announce_common = ''.join(data_list)
    
    self.pcp_data_map = (
      '\x01\x02\x03\x04d\xff\x8e\x11\n\t\x02\x04'
      '\x11\x00\x00\x00'
      '\x04\xe2\x15\xb3'
      '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff\xc8\x00\x00\x01'
    )
    
    self.pcp_data_peer = (
      '\x01\x02\x03\x04d\xff\x8e\x11\n\t\x02\x04'
      '\x11\x00\x00\x00'
      '\x04\xe2\x15\xb3'
      '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff\xc8\x00\x00\x01'
      '\x11\\\x00\x00'
      '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff\xd2\x00\x00d'
    )
    
    self.pcp_data_response_map_common = (
      '\x02\x81\x00\x01'
      '\x00\x00\x01,'
      '\x07[\xde\xc4'
      '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    )
  
  def _test_parse_pcp_opcode(self, data, fields):
    pcp_message = pcpmessage.PcpMessage.parse(data, self.pcp_client_ip)
    
    for field_name in fields.keys():
      self.assertEqual(
        pcp_message[field_name], fields[field_name],
        msg="{0}: {1} != {2}".format(field_name, pcp_message[field_name], fields[field_name])) 
  
  def test_parse_pcp_request_map(self):
    fields = self.pcp_fields_request_map_common
    fields.update(self.pcp_fields_map)
    
    self._test_parse_pcp_opcode(
      self.pcp_data_request_map_common + self.pcp_data_map, fields)
   
  def test_parse_pcp_request_peer(self):
    fields = self.pcp_fields_request_peer_common
    fields.update(self.pcp_fields_peer)
    
    self._test_parse_pcp_opcode(
      self.pcp_data_request_peer_common + self.pcp_data_peer, fields)
  
  def test_parse_pcp_request_announce(self):
    self._test_parse_pcp_opcode(
      self.pcp_data_request_announce_common, self.pcp_fields_request_announce_common)
  
  def test_parse_pcp_message_data_length_less_than_minimum(self):
    pcp_message = pcpmessage.PcpMessage.parse('\x00', self.pcp_client_ip)
    self.assertEqual(pcp_message, None)
  
  def test_parse_pcp_message_supported_version_data_length_less_than_minimum(self):
    pcp_message = pcpmessage.PcpMessage.parse(
      self.pcp_data_request_map_common[:10], self.pcp_client_ip)
    self.assertEqual(pcp_message, None)
  
  def test_parse_pcp_message_data_length_not_multiplier_of_four(self):
    pcp_message = pcpmessage.PcpMessage.parse(
      self.pcp_data_request_announce_common + '\x00', self.pcp_client_ip)
    self.assertEqual(pcp_message.parse_result, pcpmessage.PcpResultCodes.MALFORMED_REQUEST)
  
  def test_parse_pcp_message_data_length_greater_than_maximum(self):
    pcp_message = pcpmessage.PcpMessage.parse(
      self.pcp_data_request_announce_common + '\x00' * 1100, self.pcp_client_ip)
    self.assertEqual(pcp_message.parse_result, pcpmessage.PcpResultCodes.MALFORMED_REQUEST)
  
  def test_parse_pcp_request_map_invalid_data_length(self):
    pcp_message = pcpmessage.PcpMessage.parse(
      self.pcp_data_request_map_common + self.pcp_data_map[:10], self.pcp_client_ip)
    self.assertEqual(pcp_message.parse_result, pcpmessage.PcpResultCodes.MALFORMED_REQUEST)
  
  def test_parse_pcp_request_peer_invalid_data_length(self):
    pcp_message = pcpmessage.PcpMessage.parse(
      self.pcp_data_request_map_common + self.pcp_data_peer[:20], self.pcp_client_ip)
    self.assertEqual(pcp_message.parse_result, pcpmessage.PcpResultCodes.MALFORMED_REQUEST)
  
  def test_parse_pcp_request_unsupported_version(self):
    self.pcp_data_request_announce_common = '\x01' + self.pcp_data_request_announce_common[1:]
    pcp_message = pcpmessage.PcpMessage.parse(self.pcp_data_request_announce_common, self.pcp_client_ip)
    self.assertEqual(pcp_message.parse_result, pcpmessage.PcpResultCodes.UNSUPP_VERSION)
  
  def test_parse_pcp_request_unsupported_opcode(self):
    unsupported_opcode = '\x07'
    self.pcp_data_request_announce_common = (self.pcp_data_request_announce_common[0] +
      unsupported_opcode + self.pcp_data_request_announce_common[2:]) 
    pcp_message = pcpmessage.PcpMessage.parse(self.pcp_data_request_announce_common, self.pcp_client_ip)
    self.assertEqual(pcp_message.parse_result, pcpmessage.PcpResultCodes.UNSUPP_OPCODE)
  
  def test_parse_pcp_request_ip_address_mismatch(self):
    pcp_message = pcpmessage.PcpMessage.parse(self.pcp_data_request_announce_common, "192.168.1.100")
    self.assertEqual(pcp_message.parse_result, pcpmessage.PcpResultCodes.ADDRESS_MISMATCH)
  
  def test_parse_pcp_request_map_malformed_request(self):
    # Non-zero lifetime, zero protocol, non-zero internal port
    protocol = '\x00'
    self.pcp_data_map = self.pcp_data_map[:12] + protocol + self.pcp_data_map[13:]
    pcp_message = pcpmessage.PcpMessage.parse(
      self.pcp_data_request_map_common + self.pcp_data_map, self.pcp_client_ip)
    self.assertEqual(pcp_message.parse_result, pcpmessage.PcpResultCodes.MALFORMED_REQUEST)
    
  def test_parse_pcp_request_map_unsupported_zero_internal_port(self):
    internal_port = '\x00\x00'
    self.pcp_data_map = self.pcp_data_map[:16] + internal_port + self.pcp_data_map[18:]
    pcp_message = pcpmessage.PcpMessage.parse(
      self.pcp_data_request_map_common + self.pcp_data_map, self.pcp_client_ip)
    self.assertEqual(pcp_message.parse_result, pcpmessage.PcpResultCodes.UNSUPP_PROTOCOL)
  
  def test_serialize_pcp_request_map(self):
    fields = self.pcp_fields_request_map_common
    fields.update(self.pcp_fields_map)
    pcp_message = pcpmessage.PcpMessage(**fields)
    
    expected_data = self.pcp_data_request_map_common + self.pcp_data_map
    
    self.assertEqual(pcp_message.serialize(), expected_data)
  
  def test_serialize_pcp_request_peer(self):
    fields = self.pcp_fields_request_peer_common
    fields.update(self.pcp_fields_peer)
    pcp_message = pcpmessage.PcpMessage(**fields)
    
    expected_data = self.pcp_data_request_peer_common + self.pcp_data_peer
    
    self.assertEqual(pcp_message.serialize(), expected_data)
  
  def test_serialize_pcp_request_announce(self):
    pcp_message = pcpmessage.PcpMessage(**self.pcp_fields_request_announce_common)
    
    expected_data = self.pcp_data_request_announce_common
    
    self.assertEqual(pcp_message.serialize(), expected_data)
  
  def test_serialize_pcp_response_map(self):
    fields = self.pcp_fields_response_map_common
    fields.update(self.pcp_fields_map)
    pcp_message = pcpmessage.PcpMessage(**fields)
     
    expected_data = self.pcp_data_response_map_common + self.pcp_data_map
     
    self.assertEqual(pcp_message.serialize(), expected_data)
  
  def test_serialize_pcp_response_unsuccessful_result_code_copy_pcp_client_ip_addr_part(self):
    pcp_message = pcpmessage.PcpMessage(**self.pcp_fields_response_map_common)
    pcp_message.update(self.pcp_fields_map)
    pcp_message['pcp_client_ip'] = "192.168.1.1"
    
    pcp_response_data = self.pcp_data_response_map_common[:len(self.pcp_data_response_map_common)-12]
    pcp_response_data += '\x00\x00\x00\x00\x00\x00\xff\xff\xc0\xa8\x01\x01'
    
    expected_data = pcp_response_data + self.pcp_data_map
     
    self.assertEqual(pcp_message.serialize(), expected_data)
  