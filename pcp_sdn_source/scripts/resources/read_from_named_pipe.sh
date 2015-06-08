#!/bin/bash
#
# This script continuously reads from the specified named pipe.
#
#===============================================================================

clear_screen()
{
  local num_blank_lines
  
  num_blank_lines=30
  
  for ((i=0; i < num_blank_lines; i++)); do
    echo ""
  done
}

#-------------------------------------------------------------------------------

if [ -z "$1" ]; then
  echo "named pipe not specified" 1>&2
  exit 1
fi

if [ -e "$1" ] && [ ! -p "$1" ]; then
  echo "'$1': not a named pipe" 1>&2
  exit 1
fi

if [ ! -e "$1" ]; then
  mkfifo "$1"
fi

#-------------------------------------------------------------------------------

while :
do
  clear_screen
  cat "$1"
done
