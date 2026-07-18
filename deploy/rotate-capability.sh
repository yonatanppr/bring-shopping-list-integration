#!/usr/bin/env bash

set -o errexit -o nounset -o pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_deployment
new_capability=$(generate_capability)
set_env MCP_CAPABILITY "${new_capability}"
docker_compose up -d --force-recreate app
run_smoke
printf '%s\n' 'The old MCP URL is invalid. Reconfigure ChatGPT immediately:'
print_chatgpt_steps "${new_capability}"
