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
- SSH: `ssh root@my-first-server -i ~/.ssh/hetzner/hetzner_key` (Tailscale only, port 22 closed publicly)
- Service: `systemctl status mcp-server`
- Logs: `journalctl -u mcp-server -f`

## Project structure

```
/opt/mcp-server/
├── server.py          # MCP server entrypoint
├── index/             # doc indexes per API (not yet built)
│   ├── freertos.json
│   ├── espidf.json
│   ├── arduino.json
│   └── ...
├── ingest/            # scripts to download and parse API docs
│   ├── freertos.py
│   ├── espidf.py
│   └── ...
├── venv/              # Python virtual environment (not committed)
└── requirements.txt
```

## MCP tool

`lookup_symbol(symbol: str, api: str) -> str`

Returns the matching signature, parameters, return type, and a brief description.
Returns a clear "not found" if the symbol doesn't exist in the index.

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
