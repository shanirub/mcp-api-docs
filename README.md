# mcp-api-docs

A remote [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that gives Claude real-time access to API documentation — so it can verify symbol names, signatures, and parameters before answering, rather than relying on potentially stale training data.

## The problem

Claude's training data on APIs (FreeRTOS, ESP-IDF, Arduino, etc.) goes stale. Functions get renamed, signatures change, parameters are added or removed. Claude may confidently suggest a function that no longer exists.

## The solution

A self-hosted MCP server that Claude calls at query time to look up a symbol in a versioned doc index. If the symbol doesn't exist or the signature differs from what Claude expected, Claude flags it before giving an answer.

## APIs covered

| API | Status |
|-----|--------|
| FreeRTOS | planned |
| ESP-IDF | planned |
| Arduino | planned |
| Raspberry Pi | planned |
| C stdlib | planned |
| C++ STL | planned |
| Python stdlib | planned |
| bash builtins | planned |

## Architecture

```
claude.ai (Anthropic backend)
    → HTTPS → nginx (TLS termination)
        → localhost:8000 → FastMCP Python server
            → JSON doc index
```

## Infrastructure

- VPS: Hetzner, Ubuntu 24.04
- Domain: mcp.ministryofpa.ws
- TLS: Let's Encrypt (auto-renewing)
- SSH: Tailscale only (port 22 closed publicly)

## MCP tool

### `lookup_symbol(symbol, api?)`

Looks up a symbol in the doc index.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `symbol` | string | yes | Function/macro/type name to look up |
| `api` | string | no | Limit search to a specific API (e.g. `freertos`) |

Returns the symbol's signature, parameters, return type, and a brief description.
Returns a clear "not found" if the symbol doesn't exist — allowing Claude to flag the discrepancy.

## Local development

```bash
git clone git@github.com:yourname/mcp-api-docs.git
cd mcp-api-docs
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python server.py
```

## Deployment

See [CLAUDE.md](CLAUDE.md) for full server setup notes.

## Roadmap

See [ROADMAP.md](ROADMAP.md).
