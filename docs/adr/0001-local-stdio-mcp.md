# ADR 0001: Local Stdio MCP Server

## Status

Accepted

## Context

The shopping integration needs a protocol surface that a local model host can invoke.
The server holds credentials that can read and mutate a personal shopping list. A network
transport would add authentication, encryption, rate limiting, deployment, and remote
attack-surface requirements before those capabilities provide value to the first release.

The official Python MCP SDK currently has a stable 1.x line while version 2 remains a
pre-release with a migration boundary.

## Decision

Version 1 exposes only a local stdio MCP server. The model host launches the process and
provides Bring credentials through its environment. The runtime dependency is constrained
to `mcp>=1.27,<2`.

The transport stays thin: validation, deterministic list selection, duplicate handling,
and mutation behavior remain in the application service. Permanent removal requires
explicit confirmation at the tool boundary.

## Consequences

- No listening socket, remote authentication scheme, or TLS configuration is required.
- Process access and environment access are the security boundary.
- Each model host needs a local command configuration.
- Remote access and MCP 2 require separate compatibility and security decisions.
