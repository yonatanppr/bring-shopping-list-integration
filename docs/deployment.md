# Personal Cross-platform Deployment

## Scope and cost

This path is supported for one person, one Bring account, and personal non-commercial use
on a 64-bit Docker host:

- a currently supported macOS release on Intel or Apple silicon with
  [Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/);
- a Windows 10/11 system meeting
  [Docker Desktop's WSL 2 requirements](https://docs.docker.com/desktop/setup/install/windows-install/)
  on AMD64, or Windows ARM with Docker's Early Access build, using Linux containers;
- Linux on AMD64 or ARM64 with Docker Engine and the Compose plugin, including Ubuntu and
  64-bit Raspberry Pi OS.

The application and Tailscale sidecar always run as Linux containers. The published
application image supports `linux/amd64` and `linux/arm64`; Docker Desktop supplies the
Linux VM on macOS and Windows.

The server does not use the OpenAI API, so it creates no OpenAI API usage charges. Docker
Engine is open source. Tailscale's Personal plan is currently free for personal use and
[Funnel is available on all plans](https://tailscale.com/docs/features/tailscale-funnel),
but service terms and ChatGPT feature availability can change. Hardware, electricity, and
internet access remain the operator's responsibility.

Docker Desktop is free for personal use and small organizations under its current terms;
larger enterprises may require a paid Docker subscription. This personal deployment does
not require a paid Docker plan.

The Compose sidecar is pinned to Tailscale 1.98.9, which includes the Funnel path-walking
fix described in [TS-2026-009](https://tailscale.com/security-bulletins). Do not downgrade
it to an earlier 1.98 release.

## Bootstrap

Run from a clean clone on macOS or Linux:

```bash
./deploy/bootstrap.sh
```

On Windows:

```powershell
.\deploy\bootstrap.cmd
```

The bootstrap shows any Docker installation action before requesting approval. On macOS it
can install and start Docker Desktop through Homebrew; on Windows it can install and start
Docker Desktop through `winget`; on Linux it can install Docker Engine with Docker's
official installer. If that package manager is unavailable, it provides the official
manual-install URL. Tailscale and the application remain containers, so no host Python
setup is needed. Docker stores the node identity in the named
`tailscale-state` volume, so there is no reusable Tailscale auth key in `.env`.

The Bring setup call only authenticates and lists names and UUIDs. One returned list is
proposed but still requires confirmation. Multiple lists require an exact UUID. Bootstrap
does not add, complete, or remove shopping items.

If the immutable GHCR image cannot be pulled, bootstrap offers a local Docker build from
the checked-out source. It never silently switches to a mutable `latest` tag.

## Routine operations

macOS and Linux:

```bash
# Containers plus private MCP initialization check
./deploy/status.sh

# Follow bounded local logs
docker compose logs --follow app

# Stop without deleting identity or configuration
docker compose down

# Start again
docker compose up -d
```

Windows equivalents use `deploy\status.cmd`; raw `docker compose` commands are identical.

Logs use Docker's bounded `local` driver. MCP request logs contain a request ID, route
category, status, and duration. They do not contain the capability path, MCP arguments,
item names, Bring responses, email, or password. Uvicorn access logs are disabled.

## Update with rollback

Pass an explicit released semantic version:

macOS and Linux:

```bash
./deploy/update.sh 1.1.1
```

Windows:

```powershell
.\deploy\update.cmd 1.1.1
```

The script pulls the pinned image, recreates only the application container, performs a
real MCP initialize/list-tools check over loopback, and restores the previous image setting
if any step fails. Tailscale identity and the capability URL are unchanged.

## Rotate a leaked capability

macOS and Linux:

```bash
./deploy/rotate-capability.sh
```

Windows:

```powershell
.\deploy\rotate-capability.cmd
```

Rotation has no grace period: the old URL stops working as soon as the application is
recreated. The command prints only the new URL and the ChatGPT reconfiguration steps.

## Security model

Tailscale Funnel is the only public ingress and terminates HTTPS. The application shares
the sidecar's network namespace, binds only `127.0.0.1:8000`, and publishes no Docker host
port. Funnel proxies to loopback. The application then compares the entire capability path
in constant time, rewrites the accepted request to the private MCP route, and returns 404
for every other path.

Secure defaults are a 1 MiB request body, 120 requests per minute, burst 30, and four
concurrent requests. Override them in `.env` only after reviewing the resource impact:

```dotenv
MCP_HTTP_MAX_BODY_BYTES=1048576
MCP_HTTP_RATE_PER_MINUTE=120
MCP_HTTP_RATE_BURST=30
MCP_HTTP_MAX_CONCURRENCY=4
```

The HTTP transport is stateless and returns JSON. It intentionally has no public health,
metrics, discovery, or landing-page endpoint. `deploy/status.sh` validates MCP privately.

## Troubleshooting

- `tailscale funnel status` shows no URL: run
  `docker compose exec tailscale tailscale funnel --bg http://127.0.0.1:8000` and complete
  any Tailscale browser approval.
- App is unhealthy: run `docker compose logs app`; credentials and capability values must
  never be pasted into an issue.
- Bring login fails for a social-login account: set a Bring password in the Bring app.
- ChatGPT connects but cannot write: check the current ChatGPT plan support. Developer mode
  visibility alone may not grant write-capable custom MCP tools.
- To discard the Tailscale identity, first remove the device in the Tailscale admin console,
  then deliberately run `docker compose down --volumes`. This is destructive and is never
  done by the provided scripts.
- Docker Desktop reports Windows containers: switch it to Linux containers, then rerun
  bootstrap.
- Docker Desktop does not start on Windows: complete WSL 2 setup or updates from the
  [official prerequisites](https://docs.docker.com/desktop/setup/install/windows-install/),
  restart Windows if requested, and rerun bootstrap.
