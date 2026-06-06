"""
parsers/pigpio_text.py

Format-specific parser for pigpio's custom C comment style.

pigpio uses a non-standard documentation format in its headers:
    /*F*/
    int gpioSetMode(unsigned gpio, unsigned mode);
    /*D
    Brief description of the function.
    ...
    D*/

Each public function is marked by a /*F*/ sentinel on the line immediately
before its declaration. The /*D...D*/ block following the declaration contains
the prose description.

This module extracts:
    - symbol name, return type, param names and types — from the C declaration
    - description                                      — first line of /*D block

There are no explicit @param tags. Param names and types are parsed purely
from the C function signature syntax. Param descriptions are left empty.

This module is format-specific, not API-specific. It has no knowledge of
pigpio beyond the comment convention. Any C library using this style can
reuse this parser.
"""

import logging
import os
import re

log = logging.getLogger(__name__)

# Matches a C function declaration on a single line, capturing:
#   group 1: return type (everything before the last word before '(')
#   group 2: function name
#   group 3: parameter string (everything inside the outer parentheses)
_FUNC_RE = re.compile(
    r"^([\w\s\*]+?)\s+(\w+)\s*\(([^)]*)\)\s*;$"
)

# Matches a single C parameter, capturing type and name.
# Handles: "unsigned gpio", "int level", "char *buf", "void"
_PARAM_RE = re.compile(
    r"^((?:(?:unsigned|signed|const|volatile|struct|enum)\s+)?[\w\s\*]+?)\s+(\w+)\s*$"
)


def _parse_declaration(line: str) -> dict | None:
    """
    Parse a C function declaration line into symbol components.

    Returns a partial symbol dict (no api/version/header yet), or None
    if the line does not match a function declaration.
    """
    line = line.strip()
    m = _FUNC_RE.match(line)
    if not m:
        return None

    return_type  = m.group(1).strip()
    symbol       = m.group(2).strip()
    params_str   = m.group(3).strip()
    signature    = f"{return_type} {symbol}({params_str})"

    params = _parse_params(params_str)

    return {
        "symbol":    symbol,
        "kind":      "function",
        "signature": signature,
        "params":    params,
        "returns":   return_type if return_type != "void" else "",
    }


def _parse_params(params_str: str) -> list[dict]:
    """
    Parse a comma-separated C parameter string into a list of param dicts.

    Each dict has: name (str), type (str), description (str — always empty).
    """
    if not params_str or params_str == "void":
        return [{"name": "", "type": "void", "description": ""}]

    params = []
    for raw in params_str.split(","):
        raw = raw.strip()
        if not raw:
            continue

        m = _PARAM_RE.match(raw)
        if m:
            params.append({
                "name":        m.group(2).strip(),
                "type":        m.group(1).strip(),
                "description": "",
            })
        else:
            # Fallback: store the raw token, leave name empty
            params.append({
                "name":        "",
                "type":        raw,
                "description": "",
            })

    return params


def _parse_header_file(path: str, api: str, version: str) -> list[dict]:
    """
    Parse all /*F*/ / /*D...D*/ annotated functions from a single .h file.

    Returns a list of symbol dicts.
    """
    with open(path, "r", errors="replace") as f:
        lines = f.readlines()

    header  = os.path.basename(path)
    symbols = []
    i       = 0
    n       = len(lines)

    while i < n:
        # Look for the /*F*/ sentinel
        if lines[i].strip() == "/*F*/":
            # Next non-empty line should be the declaration
            i += 1
            while i < n and not lines[i].strip():
                i += 1

            if i >= n:
                break

            decl = _parse_declaration(lines[i].strip())
            i += 1

            if decl is None:
                continue

            # Collect description from the following /*D...D*/ block
            description = ""
            if i < n and lines[i].strip() == "/*D":
                i += 1
                desc_lines = []
                while i < n and lines[i].strip() != "D*/":
                    desc_lines.append(lines[i].rstrip())
                    i += 1
                # First non-empty line is the brief description
                for dl in desc_lines:
                    if dl.strip():
                        description = dl.strip()
                        break

            decl["api"]         = api
            decl["version"]     = version
            decl["header"]      = header
            decl["description"] = description
            symbols.append(decl)
        else:
            i += 1

    log.debug("Parsed %s: %d symbols", header, len(symbols))
    return symbols


def parse_source_dir(source_dir: str, api: str, version: str) -> list[dict]:
    """
    Parse all .h files in source_dir for /*F*//*D...D*/ annotated functions.

    Args:
        source_dir: Absolute path to the pigpio repo root (or headers dir).
        api:        API name to embed in every symbol dict.
        version:    Version string to embed in every symbol dict.

    Returns:
        Deduplicated list of symbol dicts sorted by symbol name.
    """
    headers = [
        "pigpio.h",
        "pigpiod_if.h",
        "pigpiod_if2.h",
    ]

    all_symbols = []
    for header in headers:
        path = os.path.join(source_dir, header)
        if not os.path.exists(path):
            log.warning("Header not found, skipping: %s", path)
            continue
        symbols = _parse_header_file(path, api, version)
        all_symbols.extend(symbols)
        log.info("Parsed %s: %d symbols", header, len(symbols))

    # Deduplicate by symbol name — pigpiod_if.h and pigpiod_if2.h share
    # many symbols with pigpio.h
    seen   = set()
    unique = []
    for s in all_symbols:
        if s["symbol"] not in seen:
            seen.add(s["symbol"])
            unique.append(s)

    unique.sort(key=lambda s: s["symbol"])
    log.info("pigpio_text: %d unique symbols from %s", len(unique), source_dir)
    return unique