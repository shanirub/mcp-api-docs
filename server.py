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

On exact miss, fuzzy matching (Jaro-Winkler) returns the closest candidates.
On exact hit, optional signature comparison reports any discrepancies between
the caller's expected signature and the indexed one.
"""

import json
import logging
import os

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from config import INDEX_DIR
from search import compare_signature, fuzzy_search

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


def _format_fuzzy_results(symbol: str, candidates: list[dict]) -> str:
    """Format fuzzy candidates into a human-readable suggestion string."""
    lines = [f"Symbol '{symbol}' not found. Did you mean:"]
    for c in candidates:
        lines.append(f"  {c['symbol']} (score: {c['score']})")
    return "\n".join(lines)


@mcp.tool()
def lookup_symbol(
    symbol: str,
    api: str,
    expected_params: list[dict],
    expected_returns: str,
) -> str:
    """
    Look up an API symbol, returning its signature, parameters, and return type.

    On exact match, optionally compares the indexed signature against the
    caller's expected signature and reports any discrepancies.

    On miss, returns the closest fuzzy matches (Jaro-Winkler similarity).

    Args:
        symbol:           Exact symbol name to look up, e.g. "xTaskCreate".
        api:              API name to search within, e.g. "freertos".
                          Pass "any" to search across all loaded APIs.
        expected_params:  List of {"name": str, "type": str} dicts
                          in declaration order, representing the caller's
                          expected parameter list.
        expected_returns: Expected return type string, e.g. "BaseType_t".

    Returns:
        Formatted symbol information, signature discrepancies if any,
        fuzzy suggestions on miss, or a clear "not found" message.
    """
    if not INDEX:
        return "Index is empty. Run `python ingest.py` on the server to build it."

    apis_to_search = list(INDEX.keys()) if api == "any" else [api]

    # --- Exact match ---
    results = []
    for api_name in apis_to_search:
        if api_name not in INDEX:
            continue
        match = INDEX[api_name].get(symbol)
        if match:
            result = _format_symbol(match)

            # Signature comparison — only when caller provides expected signature.
            if expected_params is not None or expected_returns is not None:
                discrepancies = compare_signature(
                    indexed=match,
                    expected_params=expected_params or [],
                    expected_returns=expected_returns or "",
                )
                if discrepancies:
                    result += "\n\nSignature discrepancies:\n" + "\n".join(
                        f"  - {d}" for d in discrepancies
                    )
                else:
                    result += "\n\nSignature matches."

            results.append(result)

    if results:
        return "\n\n---\n\n".join(results)

    # --- Fuzzy fallback ---
    fuzzy_candidates = []
    for api_name in apis_to_search:
        if api_name not in INDEX:
            continue
        candidates = fuzzy_search(symbol, INDEX[api_name])
        fuzzy_candidates.extend(candidates)

    # Sort across APIs by score descending, take top N.
    fuzzy_candidates.sort(key=lambda c: c["score"], reverse=True)
    fuzzy_candidates = fuzzy_candidates[:3]

    if fuzzy_candidates:
        return _format_fuzzy_results(symbol, fuzzy_candidates)

    searched = ", ".join(apis_to_search)
    return f"Symbol '{symbol}' not found in: {searched}."


if __name__ == "__main__":
    import uvicorn
    app = mcp.streamable_http_app()
    uvicorn.run(app, host="127.0.0.1", port=8000)