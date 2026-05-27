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
            → JSON doc index (per-API, per-version, loaded at startup)
```

## Server

- Host: mcp.ministryofpa.ws (Hetzner VPS, Ubuntu 24.04)
- SSH: `ssh srub@my-first-server` (Tailscale only, port 22 closed publicly)
- Service: `systemctl status mcp-server`
- Logs: `journalctl -u mcp-server -f`

## Project structure

```
/opt/mcp-server/
├── server.py                  # MCP server entrypoint (FastMCP, streamable HTTP)
├── config.py                  # centralised paths (DOCS_DIR, INDEX_DIR)
├── ingest.py                  # orchestrator: download → parse → write index
├── downloaders/               # one module per API to fetch raw docs
│   ├── freertos.py            # clones FreeRTOS-Kernel, runs Doxygen, outputs XML
│   └── ...
├── parsers/                   # one parser per doc format
│   ├── INSTRUCTIONS.md        # how to add a new parser
│   ├── base.py                # shared parser interface (ABC)
│   ├── doxygen.py             # shared Doxygen XML parser (FreeRTOS + ESP-IDF)
│   ├── freertos.py            # FreeRTOS-specific, calls doxygen.py
│   └── ...
├── index/                     # gitignored — generated JSON indexes
├── docs/                      # gitignored — raw downloaded docs + Doxygen XML
├── systemd/
│   └── mcp-server.service     # symlinked to /etc/systemd/system/
├── venv/                      # gitignored — Python virtual environment
└── requirements.txt
```

## MCP tool

`lookup_symbol(symbol: str, api: str) -> str`

Returns the matching signature, parameters, and return type.
Pass `api="any"` to search across all loaded APIs.
Returns a clear "not found" if the symbol doesn't exist in the index.

### JSON index schema (per symbol)
```json
{
    "symbol":    "xTaskCreate",
    "api":       "freertos",
    "version":   "V11.3.0",
    "kind":      "function",
    "signature": "xTaskCreate(TaskFunction_t pxTaskCode, ...)",
    "params": [
        {"name": "pxTaskCode", "type": "TaskFunction_t"},
        ...
    ],
    "returns":   "BaseType_t",
    "header":    "task.h"
}
```

## Re-ingesting docs

To rebuild the index after an API update:

```bash
cd /opt/mcp-server
source venv/bin/activate
python ingest.py              # all APIs
python ingest.py freertos     # specific API only
sudo systemctl restart mcp-server
```

## APIs covered

| API       | Status    | Format      | Symbols |
|-----------|-----------|-------------|---------|
| FreeRTOS  | ✅ live   | Doxygen XML | 1272    |
| ESP-IDF   | planned   | Doxygen XML | —       |
| Arduino   | planned   | —           | —       |
| C stdlib  | planned   | —           | —       |
| C++ STL   | planned   | —           | —       |
| Python    | planned   | —           | —       |
| bash      | planned   | —           | —       |

## Setup notes

- nginx config: `/etc/nginx/sites-enabled/default`
- TLS: Let's Encrypt via certbot, auto-renewing
- DNS: `mcp.ministryofpa.ws` A record on Namecheap → 204.168.179.208
- Tailscale SSH only — port 22 closed on Hetzner firewall
- systemd service symlinked: `/opt/mcp-server/systemd/mcp-server.service` → `/etc/systemd/system/mcp-server.service`
- SSH as `srub` (not root); `sudo` allowed for `systemctl restart mcp-server` only