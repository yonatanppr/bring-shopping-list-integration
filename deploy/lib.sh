#!/usr/bin/env bash

set -o errexit -o nounset -o pipefail

DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${DEPLOY_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_DIR}/.env"

docker_compose() {
  if docker info >/dev/null 2>&1; then
    docker compose --project-directory "${PROJECT_DIR}" "$@"
  elif [[ "$(uname -s)" == "Linux" ]] && command -v sudo >/dev/null 2>&1 \
    && sudo docker info >/dev/null 2>&1; then
    sudo docker compose --project-directory "${PROJECT_DIR}" "$@"
  else
    printf '%s\n' 'Docker is not running. Start Docker Desktop or Docker Engine first.' >&2
    return 1
  fi
}

require_deployment() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    printf '%s\n' 'Setup is incomplete: .env is missing. Run deploy/bootstrap.sh first.' >&2
    return 1
  fi
  if ! docker_compose ps --status running --services | grep -qx 'app'; then
    printf '%s\n' 'Setup is incomplete: the app service is not running. Run deploy/bootstrap.sh.' >&2
    return 1
  fi
}

dotenv_quote() {
  local value=$1
  value=${value//\\/\\\\}
  value=${value//\'/\\\'}
  printf "'%s'" "${value}"
}

set_env() {
  local name=$1 value=$2 temporary line
  temporary="${ENV_FILE}.tmp.$$"
  umask 077
  : >"${temporary}"
  if [[ -f "${ENV_FILE}" ]]; then
    while IFS= read -r line || [[ -n "${line}" ]]; do
      if [[ "${line}" != "${name}="* ]]; then
        printf '%s\n' "${line}" >>"${temporary}"
      fi
    done <"${ENV_FILE}"
  fi
  printf '%s=' "${name}" >>"${temporary}"
  dotenv_quote "${value}" >>"${temporary}"
  printf '\n' >>"${temporary}"
  chmod 600 "${temporary}"
  mv "${temporary}" "${ENV_FILE}"
}

generate_capability() {
  od -An -N32 -tx1 /dev/urandom | tr -d ' \n'
}

public_base_url() {
  local output
  if ! output=$(docker_compose exec -T tailscale tailscale funnel status 2>/dev/null); then
    return 0
  fi
  printf '%s\n' "${output}" | awk '
    {
      for (field = 1; field <= NF; field += 1) {
        if ($field ~ /^https:\/\//) {
          print $field
          exit
        }
      }
    }
  '
}

run_smoke() {
  local output
  if ! output=$(docker_compose exec -T app bring-shopping-mcp-smoke 2>/dev/null); then
    printf '%s\n' 'Private MCP initialization failed. Check the app container logs.' >&2
    return 1
  fi
  printf '%s\n' "${output}"
}

print_client_url() {
  local capability=$1 base_url
  base_url=$(public_base_url)
  if [[ -z "${base_url}" ]]; then
    printf '%s\n' 'Funnel has no public URL yet.'
    printf '%s\n' 'Run: docker compose exec tailscale tailscale funnel --bg http://127.0.0.1:8000'
    printf '%s\n' 'Then rerun deploy/status.sh.'
    return
  fi
  printf '\nMCP server URL: %s/%s/mcp\n' "${base_url%/}" "${capability}"
  printf '%s\n' 'The URL is a credential. Do not paste it into chat, logs, or issue reports.'
}
