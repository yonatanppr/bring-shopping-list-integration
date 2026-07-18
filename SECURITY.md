# Security

## Credentials

- Store Bring credentials only in process environment variables or an ignored `.env`.
- Never put credentials, access tokens, `.env` contents, or raw authentication
  responses in prompts, logs, issues, fixtures, snapshots, or commits.
- Prefer a dedicated Bring account shared only onto the lists the service needs.
- Rotate the password immediately if a credential is exposed.

## MCP Deployment

The MCP server is a privileged write interface. Local use binds to stdio. The supported
remote deployment binds to loopback in a shared Tailscale network namespace, publishes no
host port, and accepts only its exact capability URL through HTTPS Funnel. Request size,
rate, burst, and concurrency are bounded. Only the five documented tools are exposed. Do
not expose vendor credentials as MCP resources or tool arguments.

The complete capability URL is a bearer credential. Do not log, screenshot, paste, or
share it. Rotate it immediately with `deploy/rotate-capability.sh` on macOS/Linux or
`deploy\rotate-capability.cmd` on Windows after suspected exposure.
There is no grace period. Health and diagnostics stay private to the container namespace.

Treat add as low-risk but observable. Require explicit confirmation for destructive
bulk actions and permanent removal. Resolve ambiguous lists and duplicate item names
instead of guessing.

## Reporting

Do not include credentials or authentication responses in a report. Until a private
reporting channel exists, document only sanitized reproduction steps in the issue
tracker.
