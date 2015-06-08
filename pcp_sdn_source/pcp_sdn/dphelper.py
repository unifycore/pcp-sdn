"""
This module contains datapath-related functions for easier management.
"""

from collections import OrderedDict

#===============================================================================


def get_mac_addr_from_datapath(datapath):
  """
  Return the MAC address from the datapath ID.
  
  According to OpenFlow switch specification, the lower 48 bits of the datapath
  ID contains the MAC address.
  """
  
  mac_addr_int = datapath.id & 0x0000ffffffffffff
  mac_addr = format(mac_addr_int, '02x')
  
  return ':'.join(mac_addr[i:i+2] for i in range(0, 12, 2))

#===============================================================================


def add_flow_entry(datapath, match, actions, instructions=None, **kwargs):
  """
  Add a flow table entry.
  
  Use `**kwargs` to specify additional keyword arguments. Use the same keyword
  arguments as in `OFPFlowMod`.
  
  If `instructions` is None, install instruction that applies `actions` immediately.
  If `instructions` is not None, `actions` is ignored.
  """
  
  ofproto = datapath.ofproto
  parser = datapath.ofproto_parser
  
  if instructions is None:
    instructions = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
  
  message = parser.OFPFlowMod(datapath, command=ofproto.OFPFC_ADD, match=match,
                              instructions=instructions, **kwargs)
  datapath.send_msg(message)


def remove_flow_entry(datapath, match, **kwargs):
  """
  Remove a flow entry.
  """
  
  ofproto = datapath.ofproto
  parser = datapath.ofproto_parser
  
  message = parser.OFPFlowMod(datapath, command=ofproto.OFPFC_DELETE,
                              out_port=ofproto.OFPP_ANY,
                              out_group=ofproto.OFPG_ANY,
                              match=match, **kwargs)
  datapath.send_msg(message)
  

def add_instruction_goto_next_table(datapath, table_id, next_table_id, match=None, **kwargs):
  """
  Add an instruction in a flow table to go to another table.
  
  If `match` is None, match all packets.
  
  If 'priority' is not specified in `**kwargs`, it defaults to 0 (i.e. the
  lowest priority).
  """
  
  ofproto = datapath.ofproto
  parser = datapath.ofproto_parser
  
  if match is None:
    # Match all
    match = parser.OFPMatch()
  
  if 'priority' not in kwargs:
    kwargs['priority'] = 0
  
  instructions = [parser.OFPInstructionGotoTable(next_table_id)]
  message = parser.OFPFlowMod(datapath, table_id=table_id, command=ofproto.OFPFC_ADD,
    match=match, instructions=instructions, **kwargs)
  datapath.send_msg(message)


#===============================================================================


def send_packet(forwarder, packet_, out_port=None):
  """
  Send the packet out the port on the specified forwarder.
  
  If `out_port` is None, process the packet in the flow tables of the forwarder
  (i.e. the `OFPP_TABLE` port is used).
  """
  
  ofproto = forwarder.ofproto
  parser = forwarder.ofproto_parser
  
  if out_port is None:
    out_port = ofproto.OFPP_TABLE
  
  packet_.serialize()
  
  actions = [parser.OFPActionOutput(out_port)]
  packet_to_send = parser.OFPPacketOut(forwarder, buffer_id=ofproto.OFP_NO_BUFFER,
    in_port=ofproto.OFPP_CONTROLLER, actions=actions, data=packet_.data)
  
  forwarder.send_msg(packet_to_send)


#===============================================================================


def clear_datapath(datapath):
  ofproto = datapath.ofproto
  request = datapath.ofproto_parser.OFPFlowMod(
    datapath=datapath, command=ofproto.OFPFC_DELETE,
    out_port=ofproto.OFPP_ANY, out_group=ofproto.OFPG_ANY)
  datapath.send_msg(request)


#===============================================================================


class FlowTableHelper(object):
  
  """
  This class stores flow tables by their names and automatically assigns table
  IDs to them sequentially.
  """
  
  def __init__(self, flow_table_names, starting_index=0):
    """
    Parameters:
    
    * `flow_table_names` - A list of flow table names.
    """
    
    self._flow_tables = OrderedDict( (key, index + starting_index) for index, key in enumerate(flow_table_names) )
    
    self._flow_table_ids = self._flow_tables.values()
    self._flow_table_ids_and_indexes = { table_id: index for index, table_id in enumerate(self._flow_table_ids) }
  
  def __getitem__(self, table_name):
    """
    Return the ID of the flow table specified by its name.
    """
    
    return self._flow_tables[table_name]
  
  def __setitem__(self, table_name, table_id):
    """
    If the `table_name` is not defined, create a new flow table with the table
    ID. If `table_id` is already used, `table_name` is an alias to the table ID.
    """
    
    #FIXME: Need to update `self._flow_table_ids` and `self._flow_table_ids_and_indexes`
    # so that `next_table_id` still works properly.
    self._flow_tables[table_name] = table_id
  
  def next_table_id(self, table_name_or_id):
    """
    Return the next table ID from the table specified by its name or its ID.
    """
    
    try:
      # If no exception is raised, table name was passed
      table_id = self._flow_tables[table_name_or_id]
    except KeyError:
      # Table ID was passed
      table_id = table_name_or_id
    
    if table_id not in self._flow_table_ids_and_indexes:
      raise ValueError("invalid table ID")
    
    if table_id >= self._flow_table_ids[-1]:
      raise ValueError("no next table exists")
    
    index = self._flow_table_ids_and_indexes[table_id]
    
    return self._flow_table_ids[index + 1]
  
