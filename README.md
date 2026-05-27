# mcp-api-docs

A self-hosted MCP (Model Context Protocol) server that gives Claude real-time access
to API documentation for symbol verification — preventing hallucinated or outdated API
usage in responses.

## Status

Live at `mcp.ministryofpa.ws`. FreeRTOS V11.3.0 index active (1272 symbols).

## How it works

Claude's training data goes stale. When asked about an API, Claude can now call
`lookup_symbol(symbol, api)` to verify the exact signature, parameter names, types,
and return type against a locally-built documentation index — before committing to
an answer.

```
claude.ai → HTTPS → nginx (TLS) → FastMCP server → JSON index
```

## Quickstart

```bash
# SSH into server
ssh srub@my-first-server

# Rebuild the index
cd /opt/mcp-server
source venv/bin/activate
python ingest.py

# Restart server
sudo systemctl restart mcp-server
```

## Adding a new API

See `parsers/INSTRUCTIONS.md`.

## APIs

| API       | Status  | Symbols |
|-----------|---------|---------|
| FreeRTOS  | ✅ live | 1272    |
| ESP-IDF   | planned | —       |
| Arduino   | planned | —       |
| C stdlib  | planned | —       |
| C++ STL   | planned | —       |
| Python    | planned | —       |
| bash      | planned | —       |

## Docs

See `CLAUDE.md` for architecture and setup details.
See `ROADMAP.md` for planned work.