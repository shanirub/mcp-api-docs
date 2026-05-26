# MCP API Docs Server

A remote MCP (Model Context Protocol) server that allows Claude to verify API symbols,
signatures, and parameters against a local documentation index — preventing hallucinated
or outdated API usage in responses.

## What this does

Claude uses training data to reason about APIs (FreeRTOS, ESP-IDF, Arduino, C/C++, Python, bash).
Training data goes stale. This server gives Claude a tool to cross-check symbol names and
signatures at query time, before committing to an answer.

## Architecture

```
claude.ai (Anthropic backend)
    → HTTPS → nginx on Hetzner (TLS termination)
        → localhost:8000 → Python MCP server (FastMCP)
            → JSON doc index (per-API, per-version)
```

## Server

- Host: mcp.ministryofpa.ws (Hetzner VPS, Ubuntu 24.04)
- SSH: `ssh root@my-first-server` (Tailscale only, port 22 closed publicly)
- Service: `systemctl status mcp-server`
- Logs: `journalctl -u mcp-server -f`

## Project structure

```
/opt/mcp-server/
├── server.py                  # MCP server entrypoint (FastMCP, streamable HTTP)
├── config.py                  # centralised paths (DOCS_DIR, INDEX_DIR)
├── downloaders/               # one script per API to fetch raw docs
│   ├── freertos.py
│   ├── espidf.py
│   └── ...
├── parsers/                   # one parser per doc format
│   ├── INSTRUCTIONS.md        # how to add a new parser
│   ├── base.py                # shared parser interface (ABC)
│   ├── doxygen.py             # shared Doxygen XML parser (FreeRTOS + ESP-IDF)
│   ├── freertos.py            # FreeRTOS-specific, calls doxygen.py
│   └── ...
├── index/                     # gitignored — generated JSON indexes
├── docs/                      # gitignored — raw downloaded docs
├── systemd/
│   └── mcp-server.service     # symlinked to /etc/systemd/system/
├── venv/                      # gitignored — Python virtual environment
└── requirements.txt
```

## MCP tool

`lookup_symbol(symbol: str, api: str) -> str`

Returns the matching signature, parameters, return type, and a brief description.
Returns a clear "not found" if the symbol doesn't exist in the index.

### JSON index schema (per symbol)
```json
{
  "symbol": "xTaskCreate",
  "api": "freertos",
  "version": "10.6.0",
  "kind": "function",
  "signature": "BaseType_t xTaskCreate(...)",
  "params": [],
  "returns": "BaseType_t",
  "header": "task.h",
  "description": "..."
}
```

## APIs covered (planned)

- FreeRTOS
- ESP-IDF
- Arduino
- Raspberry Pi (raspi)
- C standard library
- C++ STL
- Python stdlib
- bash builtins

## Setup notes

- nginx config: `/etc/nginx/sites-enabled/default`
- TLS: Let's Encrypt via certbot, auto-renewing
- DNS: `mcp.ministryofpa.ws` A record on Namecheap → 204.168.179.208
- Tailscale SSH only — port 22 closed on Hetzner firewall
- systemd service symlinked: `/opt/mcp-server/systemd/mcp-server.service` → `/etc/systemd/system/mcp-server.service`
