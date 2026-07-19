# Deployment

## Requirements

Use a 64-bit Docker host on one of these platforms:

- a currently supported macOS release on Intel or Apple silicon with
  [Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/);
- a Windows 10/11 system meeting
  [Docker Desktop's WSL 2 requirements](https://docs.docker.com/desktop/setup/install/windows-install/)
  on AMD64, or Windows ARM with Docker's Early Access build, using Linux containers;
- Linux on AMD64 or ARM64 with Docker Engine and the Compose plugin, including Ubuntu and
  64-bit Raspberry Pi OS.

The application and Tailscale sidecar run as Linux containers. The image supports
`linux/amd64` and `linux/arm64`. You also need a Bring account, a Tailscale account, and an
MCP client that accepts a remote Streamable HTTP server.

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

Bootstrap asks before installing Docker. It uses Homebrew on macOS, `winget` on Windows,
and Docker's installer on Linux. If those options are unavailable, it prints the official
installation URL. You do not need Python on the host.

Docker stores the Tailscale node identity in the `tailscale-state` volume. `.env` contains
Bring credentials, the selected list UUID, and the MCP capability secret.

Bootstrap authenticates to Bring and lists names and UUIDs. You must confirm the exact
target UUID. Bootstrap does not change shopping items.

If Docker cannot pull the versioned image, bootstrap offers to build the checked-out source.

## Connect an MCP client

Run the status command and copy the printed HTTPS MCP URL into your client's remote MCP
server settings:

```bash
./deploy/status.sh
```

On Windows, run `deploy\status.cmd`. Select no additional authentication when the client
requires an authentication choice. The secret in the URL protects the endpoint.

Confirm that the client exposes these tools: list lists, read items, add items, complete
items, and remove items. Do not paste the URL into chat, logs, screenshots, or issue
reports. Run the capability rotation command if you expose it.

## Routine operations

macOS and Linux:

```bash
./deploy/status.sh

docker compose logs --follow app

docker compose down

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

The script pulls the versioned image, recreates the application container, checks MCP over
loopback, and restores the previous image setting on failure. It preserves Tailscale
identity and the capability URL.

## Rotate a leaked capability

macOS and Linux:

```bash
./deploy/rotate-capability.sh
```

Windows:

```powershell
.\deploy\rotate-capability.cmd
```

The old URL stops working when the application restarts. Update the MCP client with the new
URL printed by the command.

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

The HTTP transport returns JSON and exposes no public health, metrics, discovery, or
landing-page endpoint. `deploy/status.sh` checks MCP through the private container network.

## Troubleshooting

- `tailscale funnel status` shows no URL: run
  `docker compose exec tailscale tailscale funnel --bg http://127.0.0.1:8000` and complete
  any Tailscale browser approval.
- App is unhealthy: run `docker compose logs app`; credentials and capability values must
  never be pasted into an issue.
- Bring login fails for a social-login account: set a Bring password in the Bring app.
- The MCP client connects but cannot write: confirm that it permits write-capable custom
  MCP tools.
- To discard the Tailscale identity, first remove the device in the Tailscale admin console,
  then deliberately run `docker compose down --volumes`. This is destructive and is never
  done by the provided scripts.
- Docker Desktop reports Windows containers: switch it to Linux containers, then rerun
  bootstrap.
- Docker Desktop does not start on Windows: complete WSL 2 setup or updates from the
  [official prerequisites](https://docs.docker.com/desktop/setup/install/windows-install/),
  restart Windows if requested, and rerun bootstrap.
