#!/bin/bash
#
# This script continuously reads output from the specified command.
#
# This script is meant to be used in conjuction with the script running the
# topology. As such, the user can only specify the following commands:
# 
# * ryu-manager
# * ofdatapath
# * ofprotocol
#
# Arguments:
# $1 - the command to read output from
#
#===============================================================================

# Determine the directory containing this script. Taken from StackOverflow:
# http://stackoverflow.com/questions/59895/can-a-bash-script-tell-what-directory-its-stored-in
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RESOURCES_DIR="$CURRENT_DIR"'/resources'

#-------------------------------------------------------------------------------

valid_commands=( 'ryu-manager' 'ofdatapath' 'ofprotocol' )

# $1 - command name to check against the array of valid commands
is_command_valid()
{
  local command
  
  for command in "${valid_commands[@]}"; do
    if [ "$1" == "$command" ]; then
      return 0
    fi
  done
  
  return 1
}

#-------------------------------------------------------------------------------

command="$1"

if ! is_command_valid "$command" "${valid_commands[@]}"; then
  echo "'$command': invalid command" 1>&2
  echo "valid commands: ${valid_commands[@]}" 1>&2
  exit 1
fi

#-------------------------------------------------------------------------------

named_pipe="$("$RESOURCES_DIR"'/create_file.sh' --type 'pipe' "$command")"

"$RESOURCES_DIR"'/read_from_named_pipe.sh' "$named_pipe"
