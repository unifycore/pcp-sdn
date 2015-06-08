#!/bin/bash

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

sudo "$CURRENT_DIR"'/pcp_sdn_source/scripts/pcp_sdn_test_topology.sh' "$CURRENT_DIR"'/pcp_sdn_source/sdn_controller.py'
