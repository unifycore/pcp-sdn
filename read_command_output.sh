#!/bin/bash

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$CURRENT_DIR"'/pcp_sdn_source/scripts/read_command_output.sh' "$1"
