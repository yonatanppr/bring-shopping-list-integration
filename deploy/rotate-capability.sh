#!/usr/bin/env bash

set -o errexit -o nounset -o pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_deployment
new_capability=$(generate_capability)
set_env MCP_CAPABILITY "${new_capability}"
docker_compose up -d --force-recreate app
run_smoke
printf '%s\n' 'The old MCP URL is invalid. Update the MCP client:'
print_client_url "${new_capability}"
