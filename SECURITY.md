# Security

## Credentials

- Store Bring credentials only in process environment variables or an ignored `.env`.
- Never put credentials, access tokens, `.env` contents, or raw authentication
  responses in prompts, logs, issues, fixtures, snapshots, or commits.
- Prefer a dedicated Bring account shared only onto the lists the service needs.
- Rotate the password immediately if a credential is exposed.

## MCP Deployment

The future MCP server is a privileged write interface. Bind it to stdio or localhost
by default. Any remote transport must require authentication, TLS, request size and
rate limits, and an allowlist of exposed tools. Do not expose vendor credentials as
MCP resources or tool arguments.

Treat add as low-risk but observable. Require explicit confirmation for destructive
bulk actions and permanent removal. Resolve ambiguous lists and duplicate item names
instead of guessing.

## Reporting

Do not include credentials or authentication responses in a report. Until a private
reporting channel exists, document only sanitized reproduction steps in the issue
tracker.
