#!/usr/bin/env bash

set -o errexit -o nounset -o pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

confirm() {
  local prompt=$1 answer
  read -r -p "${prompt} [y/N] " answer
  [[ "${answer}" == "y" || "${answer}" == "Y" ]]
}

check_platform() {
  local architecture system
  architecture=$(uname -m)
  system=$(uname -s)
  case "${system}" in
    Darwin | Linux) ;;
    *) printf 'Unsupported Unix host: %s. On Windows use deploy\\bootstrap.cmd.\n' "${system}" >&2; exit 1 ;;
  esac
  case "${architecture}" in
    x86_64 | aarch64 | arm64) ;;
    *) printf 'Unsupported architecture: %s (use 64-bit amd64 or arm64).\n' "${architecture}" >&2; exit 1 ;;
  esac
  if [[ "$(getconf LONG_BIT)" != "64" ]]; then
    printf '%s\n' 'A 64-bit operating system is required.' >&2
    exit 1
  fi
}

docker_ready() {
  docker info >/dev/null 2>&1 || {
    [[ "$(uname -s)" == "Linux" ]] && command -v sudo >/dev/null 2>&1 \
      && sudo docker info >/dev/null 2>&1
  }
}

wait_for_docker() {
  local attempts=0
  until docker_ready; do
    ((attempts += 1))
    if [[ ${attempts} -ge 90 ]]; then
      printf '%s\n' 'Docker did not become ready within three minutes.' >&2
      exit 1
    fi
    sleep 2
  done
}

install_docker_if_needed() {
  local installer system
  system=$(uname -s)
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    if ! docker_ready; then
      if [[ "${system}" == "Darwin" ]]; then
        printf '%s\n' 'Starting Docker Desktop...'
        open -a Docker
      fi
      wait_for_docker
    fi
    return
  fi
  if [[ "${system}" == "Darwin" ]]; then
    printf '%s\n' 'Docker Desktop with the Compose plugin is required.'
    if command -v brew >/dev/null 2>&1; then
      confirm 'Install Docker Desktop with Homebrew now?' || exit 1
      brew install --cask docker
      open -a Docker
      wait_for_docker
      return
    fi
    printf '%s\n' 'Install Docker Desktop from https://docs.docker.com/desktop/setup/install/mac-install/ and rerun this command.' >&2
    exit 1
  fi
  printf '%s\n' 'Docker Engine with the Compose plugin is required.'
  printf '%s\n' 'The next step downloads https://get.docker.com and runs it with sudo.'
  confirm 'Install Docker now?' || exit 1
  command -v curl >/dev/null 2>&1 || { printf '%s\n' 'curl is required.' >&2; exit 1; }
  installer=$(mktemp)
  curl --fail --show-error --silent --location https://get.docker.com --output "${installer}"
  sudo sh "${installer}"
  rm -f "${installer}"
  wait_for_docker
}

configure_environment() {
  local email password hostname capability
  printf '%s\n' 'Bring credentials are written only to .env with mode 0600.'
  read -r -p 'Bring email: ' email
  read -r -s -p 'Bring password: ' password
  printf '\n'
  [[ -n "${email}" && -n "${password}" ]] || { printf '%s\n' 'Email and password are required.' >&2; exit 1; }
  read -r -p 'Tailscale device name [bring-shopping]: ' hostname
  hostname=${hostname:-bring-shopping}
  [[ "${hostname}" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$ ]] || { printf '%s\n' 'Invalid device name.' >&2; exit 1; }
  capability=$(generate_capability)
  set_env BRING_EMAIL "${email}"
  set_env BRING_PASSWORD "${password}"
  set_env BRING_REQUEST_TIMEOUT_SECONDS "20"
  set_env MCP_CAPABILITY "${capability}"
  set_env MCP_HTTP_MAX_BODY_BYTES "1048576"
  set_env MCP_HTTP_RATE_PER_MINUTE "120"
  set_env MCP_HTTP_RATE_BURST "30"
  set_env MCP_HTTP_MAX_CONCURRENCY "4"
  set_env TAILSCALE_HOSTNAME "${hostname}"
  set_env BRING_SHOPPING_IMAGE "ghcr.io/yonatanppr/bring-shopping-list-integration:1.1.0"
}

prepare_image() {
  if docker_compose pull app; then
    return
  fi
  printf '%s\n' 'The published image could not be pulled.'
  confirm 'Build the same image locally from this clone?' || exit 1
  docker_compose build app
}

enroll_tailscale() {
  docker_compose up -d tailscale
  if docker_compose exec -T tailscale tailscale ip -4 >/dev/null 2>&1; then
    return
  fi
  printf '%s\n' 'Open the one-time URL shown below and approve this device.'
  docker_compose exec tailscale tailscale login --timeout=10m
}

select_list() {
  local -a lines
  local selected_uuid answer line uuid
  lines=()
  while IFS= read -r line; do
    lines+=("${line}")
  done < <(docker_compose run --rm --no-deps app bring-shopping lists)
  if [[ ${#lines[@]} -eq 0 ]]; then
    printf '%s\n' 'No Bring shopping lists are available to this account.' >&2
    exit 1
  fi
  printf '\nAvailable Bring lists (name, UUID):\n'
  printf '  %s\n' "${lines[@]}"
  if [[ ${#lines[@]} -eq 1 ]]; then
    selected_uuid=${lines[0]##*$'\t'}
    read -r -p "Use this list UUID (${selected_uuid})? [y/N] " answer
    [[ "${answer}" == "y" || "${answer}" == "Y" ]] || exit 1
  else
    read -r -p 'Enter the exact UUID to use: ' selected_uuid
    local matches=0
    for line in "${lines[@]}"; do
      uuid=${line##*$'\t'}
      [[ "${uuid}" == "${selected_uuid}" ]] && ((matches += 1))
    done
    [[ ${matches} -eq 1 ]] || { printf '%s\n' 'That UUID was not listed exactly once.' >&2; exit 1; }
  fi
  set_env BRING_LIST_UUID "${selected_uuid}"
}

start_and_expose() {
  local capability
  docker_compose up -d app
  run_smoke
  printf '%s\n' 'Enabling the public HTTPS Funnel. Tailscale may show one approval URL.'
  docker_compose exec tailscale tailscale funnel --bg http://127.0.0.1:8000
  # Read the just-created capability without exposing credentials or evaluating .env.
  capability=$(sed -n "s/^MCP_CAPABILITY='\([0-9a-f]\{64\}\)'$/\1/p" "${ENV_FILE}")
  [[ -n "${capability}" ]] || { printf '%s\n' 'Could not read MCP capability.' >&2; exit 1; }
  print_chatgpt_steps "${capability}"
}

main() {
  cd "${PROJECT_DIR}"
  check_platform
  install_docker_if_needed
  configure_environment
  prepare_image
  enroll_tailscale
  select_list
  start_and_expose
  printf '\nSetup complete. Follow docs/chatgpt-pilot.md for the reversible pilot.\n'
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
