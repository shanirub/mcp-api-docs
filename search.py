"""
search.py

Symbol search utilities: fuzzy matching and signature comparison.

Fuzzy matching uses Jaro-Winkler similarity (via rapidfuzz), which weights
prefix matches more heavily than mid-string matches — well-suited for
camelCase API symbols where the prefix carries semantic meaning.

Signature comparison diffs expected vs indexed params and return type,
reporting all discrepancies without filtering — callers decide what to act on.
"""

from __future__ import annotations

import logging

from rapidfuzz import process, utils
from rapidfuzz.distance import JaroWinkler

from config import FUZZY_THRESHOLD, FUZZY_TOP_N

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fuzzy search
# ---------------------------------------------------------------------------

def fuzzy_search(
    symbol: str,
    symbols: dict[str, dict],
    top_n: int = FUZZY_TOP_N,
    threshold: float = FUZZY_THRESHOLD,
) -> list[dict]:
    """
    Find the closest symbol names to `symbol` within `symbols`.

    Args:
        symbol:    Query symbol name.
        symbols:   Inner index dict: { symbol_name: symbol_data }.
                   Caller is responsible for pre-slicing to the relevant API.
        top_n:     Maximum number of candidates to return.
        threshold: Minimum Jaro-Winkler similarity score (0.0–1.0) to include
                   a candidate. Candidates below this are discarded.

    Returns:
        List of dicts, sorted by score descending:
            [{"symbol": str, "score": float, "data": symbol_dict}, ...]
        Empty list if no candidates meet the threshold.
    """
    if not symbols:
        return []

    # process.extract returns (match, score, key) tuples.
    # scorer=JaroWinkler.normalized_similarity gives a 0.0–1.0 score.
    # processor=utils.default_process lowercases and strips whitespace,
    # making matching case-insensitive.
    matches = process.extract(
        symbol,
        symbols.keys(),
        scorer=JaroWinkler.normalized_similarity,
        processor=utils.default_process,
        limit=top_n,
    )

    results = []
    for match_name, score, _ in matches:
        if score < threshold:
            continue
        results.append({
            "symbol": match_name,
            "score":  round(score, 4),
            "data":   symbols[match_name],
        })

    return results


# ---------------------------------------------------------------------------
# Signature comparison
# ---------------------------------------------------------------------------

def compare_signature(
    indexed: dict,
    expected_params: list[dict],
    expected_returns: str,
) -> list[str]:
    """
    Diff expected signature against the indexed symbol.

    Args:
        indexed:          Symbol dict from the index (as returned by lookup).
        expected_params:  List of {"name": str, "type": str} dicts,
                          in declaration order.
        expected_returns: Expected return type string, e.g. "BaseType_t".

    Returns:
        List of human-readable discrepancy strings.
        Empty list means signatures match.
    """
    discrepancies = []

    # --- Return type ---
    indexed_returns = indexed.get("returns", "")
    if indexed_returns != expected_returns:
        discrepancies.append(
            f"Return type: expected '{expected_returns}', "
            f"indexed '{indexed_returns}'"
        )

    # --- Parameter count ---
    indexed_params = indexed.get("params", [])
    if len(indexed_params) != len(expected_params):
        discrepancies.append(
            f"Parameter count: expected {len(expected_params)}, "
            f"indexed {len(indexed_params)}"
        )
        # Can't meaningfully compare individual params if counts differ.
        return discrepancies

    # --- Per-parameter comparison ---
    for i, (exp, idx) in enumerate(zip(expected_params, indexed_params)):
        exp_type = exp.get("type", "")
        idx_type = idx.get("type", "")
        exp_name = exp.get("name", "")
        idx_name = idx.get("name", "")

        if exp_type != idx_type:
            discrepancies.append(
                f"Param {i} type: expected '{exp_type}', indexed '{idx_type}'"
            )
        if exp_name != idx_name:
            discrepancies.append(
                f"Param {i} name: expected '{exp_name}', indexed '{idx_name}' "
                f"(cosmetic — types match)" if exp_type == idx_type
                else f"Param {i} name: expected '{exp_name}', indexed '{idx_name}'"
            )

    return discrepancies