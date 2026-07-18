#!/usr/bin/env bash

set -o errexit -o nounset -o pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_deployment
docker_compose ps
run_smoke
capability=$(sed -n "s/^MCP_CAPABILITY='\([0-9a-f]\{64\}\)'$/\1/p" "${ENV_FILE}")
[[ -n "${capability}" ]] || { printf '%s\n' 'MCP capability is missing.' >&2; exit 1; }
print_chatgpt_steps "${capability}"
