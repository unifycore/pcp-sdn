#!/bin/bash
#
# This script creates the test topology for the "Port Control Protocol over SDN"
# scenario.
#
# Test topology:
#
#         Controller
#             |
# Host 1 - Forwarder - Host 2
#
# Host 1 is in an access network and has a private IP address.
# Host 2 is in an external network and has a public IP address.
#
# Forwarder:
# * forwards PCP requests from the internal host to the controller,
# * forwards PCP responses from the controller to the internal host,
# * translates IP addresses and ports.
# 
# Controller:
# * processes PCP requests from Host 1,
# * creates NAT table entries in the forwarder,
# * sends PCP responses to Host 1.
#
# Note: This script must be run as root.
#
#-------------------------------------------------------------------------------
#
# Arguments:
# $1 - name of the Python script to execute as the ryu controller application
#
#===============================================================================

# Taken from StackOverflow:
# http://stackoverflow.com/questions/59895/can-a-bash-script-tell-what-directory-its-stored-in
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESOURCES_DIR="$CURRENT_DIR"'/resources'

#-------------------------------------------------------------------------------

if [ "$EUID" -ne 0 ]; then
  echo "This script must be run as root" 1>&2
  exit 1
fi

if [ ! -f "$1" ]; then
  echo "error: $1: Invalid ryu controller application script" 1>&2
  exit 1
fi

#-------------------------------------------------------------------------------

create_topology()
{
  ip netns add 'host1'
  ip netns add 'host2'
  
  ip link add 'host1_fw' type veth peer name 'fw_host1'
  ip link add 'host2_fw' type veth peer name 'fw_host2'
  
  ip link set 'host1_fw' netns 'host1'
  ip link set 'host2_fw' netns 'host2'
  
  ip netns exec 'host1' ifconfig 'host1_fw' '172.16.0.100/24' up
  ip netns exec 'host1' route add default gw '172.16.0.1' 'host1_fw'
  
  ip netns exec 'host2' ifconfig 'host2_fw' '200.0.0.200/24' up
  ip netns exec 'host2' route add default gw '200.0.0.1' 'host2_fw'
  
  # Make sure that hosts can send any packets. This is due to a lack of proper
  # routing in the test network.
  ip netns exec 'host1' route add -net '0.0.0.0' netmask '0.0.0.0' dev 'host1_fw'
  ip netns exec 'host2' route add -net '0.0.0.0' netmask '0.0.0.0' dev 'host2_fw'
}

delete_topology()
{
  ip netns delete 'host1'
  ip netns delete 'host2'
}

# Terminate all background processes created by this script.
terminate_bg_processes()
{
  local bg_processes
  
  bg_processes="$(jobs -p)"
  
  if [ -n "$bg_processes" ]; then
    echo "$bg_processes" | xargs kill
  fi
}

#-------------------------------------------------------------------------------

_is_cleaned_up=0

_cleanup()
{
  terminate_bg_processes
  delete_topology
}

cleanup()
{
  if [ "$_is_cleaned_up" -eq 0 ]; then
    _cleanup
    _is_cleaned_up=1
  fi
}

#-------------------------------------------------------------------------------

redirect_output()
{
  local command
  local output_file
  
  command="$1"
  output_file="$("$RESOURCES_DIR"'/create_file.sh' --type pipe "$command")"
  
  "$command" "${@:2}" > "$output_file" 2>&1
}

#===============================================================================

trap 'cleanup' SIGHUP SIGINT SIGTERM EXIT

#-------------------------------------------------------------------------------

create_topology

# Run the controller.
redirect_output ryu-manager "$1" --observe-links --verbose &

# Create and run an OpenFlow switch.
redirect_output ofdatapath --interfaces='fw_host1','fw_host2' 'punix:/tmp/fw.socket' --verbose &

# Connect the OpenFlow switch to the controller.
redirect_output ofprotocol 'unix:/tmp/fw.socket' 'tcp:127.0.0.1:6633' --verbose &

#-------------------------------------------------------------------------------

echo "To terminate this script, press ctrl+C."

wait
