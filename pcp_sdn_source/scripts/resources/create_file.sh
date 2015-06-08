#!/bin/bash
#
# This script creates a file of the specified type in the "[home]/tmp" directory.
#
#===============================================================================

PROGNAME="$(basename "$0")"

#-------------------------------------------------------------------------------

TEMP_DIR="$HOME"'/tmp'

if [ ! -d "$TEMP_DIR" ]; then
  mkdir -p "$TEMP_DIR"
fi

#-------------------------------------------------------------------------------

option_do_not_create=0
option_file_type='file'
option_permissions=766
option_no_output=0

USAGE="
Create a file in the home temporary directory with the specified base name and print the file path.

Usage: $PROGNAME [options]... [base name]

Options:
-n, --do-not-create - do not create the file if it does not exist
-t [type], --type [type] - file type to create: 'file', 'dir', 'pipe'; if the file already exists, it will be left intact, even if it is a file of different type
-p [perms], --permissions [perms] - file permissions to assign; if the file exists, permissions are left intact
-s, --no-output - do not print the file path
-h, --help
"

usage_and_exit()
{
  # Print the usage string to stderr and exit.
  # $1 - usage string to print

  echo "$USAGE" 1>&2
  exit 1
}

#-------------------------------------------------------------------------------

# Parse options

while [[ "${1:0:1}" = "-" && "$1" != "--" ]]; do
	case "$1" in
    -n | --do-not-create )
      option_do_not_create=1
      shift
    ;;
    -t | --type )
      option_file_type="$2"
      shift
    ;;
    -p | --permissions )
      option_permissions="$2"
      shift
    ;;
    -s | --no-output )
      option_no_output=1
      shift
    ;;
    -h | --help )
      usage_and_exit
    ;;
    * )
      if [ -n "$1" ]; then
        echo "${PROGNAME}: unknown option: '$1'" 1>&2
      fi
      usage_and_exit
    ;;
	esac
		
	shift
done

if [ "$1" = "--" ]; then
  shift
fi

#-------------------------------------------------------------------------------

if [ -z "$1" ]; then
  echo "${PROGNAME}: base name not specified"
  usage_and_exit
fi

#-------------------------------------------------------------------------------

file_to_create="$TEMP_DIR"'/'"$1"'-log'

if [ "${option_do_not_create}" -eq 0 ]; then
  case "${option_file_type}" in
    file )
      if [ ! -e "$file_to_create" ]; then
        : > "$file_to_create"
        chmod "${option_permissions}" "$file_to_create"
      fi
    ;;
    dir )
      if [ ! -e "$file_to_create" ]; then
        mkdir -p "$file_to_create" --mode="${option_permissions}"
      fi
    ;;
    pipe )
      if [ ! -e "$file_to_create" ]; then
        mkfifo "$file_to_create" --mode="${option_permissions}"
      fi
    ;;
    * )
      echo "${PROGNAME}: invalid type: '$1'" 1>&2
      usage_and_exit
    ;;
  esac
fi

#-------------------------------------------------------------------------------

if [ "${option_no_output}" -eq 0 ]; then
  echo "$file_to_create"
fi
