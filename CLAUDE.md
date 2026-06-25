# MCP API Docs Server

A remote MCP (Model Context Protocol) server that allows Claude to verify API symbols,
signatures, and parameters against a local documentation index — preventing hallucinated
or outdated API usage in responses.

## What this does

Claude uses training data to reason about APIs (FreeRTOS, ESP-IDF, Arduino, C/C++, Python, bash).
Training data goes stale. This server gives Claude a tool to cross-check symbol names and
signatures at query time, before committing to an answer.

The tool supports:
- **Exact lookup** — returns signature, parameters, and return type
- **Fuzzy matching** — tolerates typos, returns top 3 closest matches with confidence scores
- **Signature comparison** — diffs expected vs indexed params and return type, reports discrepancies
- **Multi-API search** — pass `api="any"` to search across all loaded indexes

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
├── search.py                  # fuzzy search (Jaro-Winkler) + signature comparison
├── config.py                  # centralised paths, fuzzy thresholds, ESP-IDF component list
├── ingest.py                  # orchestrator: download → parse → write index
├── downloaders/               # one module per API family to fetch raw docs
│   ├── freertos.py            # shallow clone of FreeRTOS-Kernel, runs Doxygen
│   └── esp_idf.py             # sparse checkout of ESP-IDF components, runs Doxygen per component
├── parsers/                   # one parser per doc format
│   ├── INSTRUCTIONS.md        # how to add a new parser
│   ├── base.py                # shared parser interface (ABC)
│   ├── doxygen.py             # shared Doxygen XML parser (FreeRTOS + ESP-IDF)
│   ├── freertos.py            # FreeRTOS-specific, delegates to doxygen.py
│   └── esp_idf.py             # ESP-IDF-specific, delegates to doxygen.py
├── index/                     # gitignored — generated JSON indexes (one per API)
├── docs/                      # gitignored — raw downloaded docs + Doxygen XML
├── systemd/
│   └── mcp-server.service     # symlinked to /etc/systemd/system/
├── venv/                      # gitignored — Python virtual environment
└── requirements.txt
```

## MCP tool

`lookup_symbol(symbol, api, expected_params, expected_returns) -> str`

All four arguments are required.

- `symbol` — exact symbol name to look up, e.g. `"xTaskCreate"`
- `api` — API name, e.g. `"freertos"`, `"esp_driver_i2c"`. Pass `"any"` to search all.
- `expected_params` — list of `{"name": str, "type": str}` dicts in declaration order
- `expected_returns` — expected return type string, e.g. `"BaseType_t"`

On exact hit: returns symbol info + signature comparison result (match or discrepancies).
On miss: returns top 3 fuzzy candidates above threshold with confidence scores.

### JSON index schema (per symbol)
```json
{
    "symbol":    "xTaskCreate",
    "api":       "freertos",
    "version":   "V11.3.0",
    "kind":      "function",
    "signature": "BaseType_t xTaskCreate(TaskFunction_t pxTaskCode, ...)",
    "params": [
        {"name": "pxTaskCode", "type": "TaskFunction_t"},
        ...
    ],
    "returns":   "BaseType_t",
    "header":    "task.h"
}
```

## APIs covered

| API                | Status  | Format      | Symbols |
|--------------------|---------|-------------|---------|
| FreeRTOS           | ✅ live | Doxygen XML | 1272    |
| esp_driver_i2c     | ✅ live | Doxygen XML | 21      |
| esp_driver_uart    | ✅ live | Doxygen XML | 77      |
| esp_driver_gpio    | ✅ live | Doxygen XML | 60      |
| esp_wifi           | ✅ live | Doxygen XML | 457     |
| esp_http_server    | ✅ live | Doxygen XML | 75      |
| esp_timer          | ✅ live | Doxygen XML | 17      |
| esp_isotp          | ✅ live | Doxygen XML | 6    |  (idf-extra-components, master)
| isotp_c            | ✅ live | Doxygen XML | 9    |  (SimonCahill/isotp-c submodule)
| Arduino            | planned | —           | —       |
| C stdlib           | planned | —           | —       |
| C++ STL            | planned | —           | —       |
| Python             | planned | —           | —       |
| bash               | planned | —           | —       |

## Re-ingesting docs

```bash
cd /opt/mcp-server
source venv/bin/activate

python ingest.py                  # all APIs
python ingest.py freertos         # FreeRTOS only
python ingest.py esp_idf          # all ESP-IDF components
python ingest.py esp_driver_i2c   # one ESP-IDF component only

sudo systemctl restart mcp-server
```

## Adding a new API

See `parsers/INSTRUCTIONS.md`.

For ESP-IDF components: add the component to `ESP_IDF_COMPONENTS` in `config.py` —
no other changes needed.

For a new API family (different doc format): add a downloader under `downloaders/`,
a parser under `parsers/`, and register it in `ingest.py`.

## config.py constants

- `DOCS_DIR` — raw downloaded docs and Doxygen XML
- `INDEX_DIR` — generated JSON indexes
- `FUZZY_THRESHOLD` — minimum Jaro-Winkler score (0.0–1.0) for fuzzy candidates (default 0.85)
- `FUZZY_TOP_N` — maximum fuzzy candidates returned (default 3)
- `ESP_IDF_COMPONENTS` — dict of component name → include subpath for sparse checkout

## Known issues

- `esp_driver_gpio`: `rtc_io_number_get` and `rtc_gpio_get_level` not indexed.
  Both are behind `#if SOC_RTCIO_PIN_COUNT > 0` — Doxygen `PREDEFINED` cannot evaluate
  numeric comparisons, only simple defined/undefined substitutions.

## Setup notes

- nginx config: `/etc/nginx/sites-enabled/default`
- TLS: Let's Encrypt via certbot, auto-renewing
- DNS: `mcp.ministryofpa.ws` A record on Namecheap → 204.168.179.208
- Tailscale SSH only — port 22 closed on Hetzner firewall
- systemd service symlinked: `/opt/mcp-server/systemd/mcp-server.service` → `/etc/systemd/system/mcp-server.service`
- SSH as `srub` (not root); `sudo` allowed for `systemctl restart mcp-server` only
- Python deps: `fastmcp`, `uvicorn`, `rapidfuzz`