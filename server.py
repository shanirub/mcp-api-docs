"""
server.py

MCP server entrypoint.

Loads all available API indexes from INDEX_DIR at startup into memory.
The in-memory index is a nested dict:
    {
        "freertos": {
            "xTaskCreate": { ...symbol dict... },
            ...
        },
        ...
    }

lookup_symbol() searches by exact symbol name within the requested API,
or across all APIs if api="any".
"""

import json
import logging
import os

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from config import INDEX_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

mcp = FastMCP(
    "api-docs",
    transport_security=TransportSecuritySettings(
        allowed_hosts=["mcp.ministryofpa.ws"],
        allowed_origins=["https://mcp.ministryofpa.ws"],
    ),
)


def _load_index() -> dict[str, dict[str, dict]]:
    """
    Load all <api>.json files from INDEX_DIR into memory.

    Returns a nested dict: { api_name: { symbol_name: symbol_dict } }
    Missing or empty INDEX_DIR is not an error — server starts with empty index.
    """
    index = {}

    if not os.path.isdir(INDEX_DIR):
        log.warning("INDEX_DIR does not exist: %s — run ingest.py first", INDEX_DIR)
        return index

    for filename in os.listdir(INDEX_DIR):
        if not filename.endswith(".json"):
            continue
        api_name   = filename[:-5]          # strip .json
        index_path = os.path.join(INDEX_DIR, filename)
        try:
            with open(index_path) as f:
                symbols = json.load(f)
            index[api_name] = {s["symbol"]: s for s in symbols}
            log.info("Loaded %d symbols for API '%s'", len(index[api_name]), api_name)
        except Exception as e:
            log.error("Failed to load index %s: %s", index_path, e)

    return index


# Load once at startup — stays in memory for the lifetime of the process.
INDEX = _load_index()


def _format_symbol(s: dict) -> str:
    """Format a symbol dict into a human-readable string for Claude."""
    lines = [
        f"Symbol:    {s['symbol']}",
        f"API:       {s['api']} {s['version']}",
        f"Kind:      {s['kind']}",
        f"Header:    {s['header']}",
        f"Signature: {s['signature']}",
    ]

    if s.get("params"):
        lines.append("Parameters:")
        for p in s["params"]:
            lines.append(f"  {p['type']} {p['name']}")

    if s.get("returns"):
        lines.append(f"Returns:   {s['returns']}")

    return "\n".join(lines)


@mcp.tool()
def lookup_symbol(symbol: str, api: str) -> str:
    """
    Look up an API symbol, returning its signature, parameters, and description.

    Args:
        symbol: Exact symbol name to look up, e.g. "xTaskCreate".
        api:    API name to search within, e.g. "freertos".
                Pass "any" to search across all loaded APIs.

    Returns:
        Formatted symbol information, or a clear "not found" message.
    """
    if not INDEX:
        return (
            "Index is empty. Run `python ingest.py` on the server to build it."
        )

    apis_to_search = (
        list(INDEX.keys()) if api == "any" else [api]
    )

    results = []
    for api_name in apis_to_search:
        if api_name not in INDEX:
            continue
        match = INDEX[api_name].get(symbol)
        if match:
            results.append(_format_symbol(match))

    if not results:
        searched = ", ".join(apis_to_search)
        return f"Symbol '{symbol}' not found in: {searched}."

    return "\n\n---\n\n".join(results)


if __name__ == "__main__":
    import uvicorn
    app = mcp.streamable_http_app()
    uvicorn.run(app, host="127.0.0.1", port=8000)