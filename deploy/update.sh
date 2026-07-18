#!/usr/bin/env bash

set -o errexit -o nounset -o pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_deployment
version=${1:-}
version=${version#v}
if [[ ! "${version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  printf 'Usage: %s VERSION (for example: 1.1.1)\n' "$0" >&2
  exit 2
fi

backup=$(mktemp)
chmod 600 "${backup}"
cp "${ENV_FILE}" "${backup}"
trap 'rm -f "${backup}"' EXIT

rollback() {
  local exit_code=$?
  trap - ERR
  set +o errexit
  cp "${backup}" "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
  docker_compose up -d --force-recreate app
  rm -f "${backup}"
  printf '%s\n' 'Update failed; the prior image configuration was restored.' >&2
  exit "${exit_code}"
}
trap rollback ERR

set_env BRING_SHOPPING_IMAGE "ghcr.io/yonatanppr/bring-shopping-list-integration:${version}"
docker_compose pull app
docker_compose up -d --force-recreate app
run_smoke

trap - ERR
printf 'Updated successfully to %s.\n' "${version}"
