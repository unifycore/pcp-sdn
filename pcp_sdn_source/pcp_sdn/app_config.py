"""
This module loads configuration data (NAT pool, flow entry priorities, PCP
ports, etc.) for the network application used in other modules.
"""

#===============================================================================

import json

import os
import inspect
import logging

from collections import OrderedDict

#===============================================================================


class _AppConfig(object):
  
  """
  This class:
  * loads data from the configuration file for the network application,
  * generates configuration file with factory default values if missing.
  
  This class stores the configuration data as read-only. 
  """
  
  def __init__(self, config_filename, factory_default_config):
    """
    Load configuration from `config_filename`. If missing, load configuration
    from the `factory_default_config` dict.
    """
    
    self._config_filename = config_filename
    self._factory_default_config = factory_default_config
    
    self._config = self._load_config()
    
    if self._config is None:
      self._config = self._factory_default_config
      self._create_config()
  
  def __getitem__(self, config_entry_name):
    return self._config[config_entry_name]
  
  def _load_config(self):
    """
    Load the application configuration from the specified file and return the
    configuration as a dict.
    
    If loading fails (e.g. due to missing file, no permission to read or invalid
    format), return None.
    """
    
    def _error_message(message):
      logging.info("Failed to read from config file '{0}'; reason: {1}".format(
                   self._config_filename, message))
    
    try:
      config_file = open(self._config_filename, "r")
    except (IOError, OSError) as e:
      _error_message(e.message)
      return None
    
    try:
      self._config = json.load(config_file)
    except ValueError as e:
      _error_message(e.message)
      return None
    
    config_file.close()
    
    return self._config
  
  def _create_config(self):
    logging.info("Creating config file '{0}'".format(self._config_filename))
    try:
      config_file = open(self._config_filename, "w")
    except (IOError, OSError) as e:
      # Don't do anything, just print a warning message.
      logging.info("Failed to create config file '{0}'; reason: {1}".format(
                   self._config_filename, e.message))
    else:
      json.dump(self._factory_default_config, config_file, indent=2)
      config_file.close()


#===============================================================================

_FACTORY_DEFAULT_CONFIG = OrderedDict()

_FACTORY_DEFAULT_CONFIG['pcp_server_listening_port'] = 5351
_FACTORY_DEFAULT_CONFIG['pcp_client_multicast_port'] = 5350

_FACTORY_DEFAULT_CONFIG['default_pcp_map_assigned_lifetime_seconds'] = 0
_FACTORY_DEFAULT_CONFIG['default_pcp_peer_assigned_lifetime_seconds'] = 0

_FACTORY_DEFAULT_CONFIG['default_nat_flow_entry_priority'] = 1
_FACTORY_DEFAULT_CONFIG['default_mac_modifying_flow_entries_priority'] = 1
_FACTORY_DEFAULT_CONFIG['default_arp_forwarding_priority'] = 2
_FACTORY_DEFAULT_CONFIG['default_pcp_forwarding_priority'] = 3

_FACTORY_DEFAULT_CONFIG['default_nat_pool_config'] = OrderedDict([
  ('internal_ip_low_end', "172.16.0.2"),
  ('internal_ip_high_end', "172.16.255.254"),
  ('internal_port_low_end', 1),
  ('internal_port_high_end', 65535),
  ('external_ip_low_end', "200.0.0.2"),
  ('external_ip_high_end', "200.0.255.254"),
  ('external_port_low_end', 49152),
  ('external_port_high_end', 65535),
  ('ip_allocation_type', 0),    # NatTableAllocationType.ROUND_ROBIN
  ('port_allocation_type', 1)   # NatTableAllocationType.RANDOM
])

#===============================================================================

_CURRENT_DIR = os.path.dirname(inspect.getfile(inspect.currentframe()))
_CONFIG_FILE_DIR = os.path.dirname(_CURRENT_DIR)
_CONFIG_FILENAME = os.path.join(_CONFIG_FILE_DIR, "app_config.json")


def init():
  """
  Load (initialize) the network application configuration data.
  """
  
  global _CONFIG_FILENAME, _FACTORY_DEFAULT_CONFIG
  global app_config
  
  app_config = _AppConfig(_CONFIG_FILENAME, _FACTORY_DEFAULT_CONFIG)
