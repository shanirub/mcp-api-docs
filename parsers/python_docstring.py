"""
parsers/python_docstring.py

Format-specific parser for untyped Python source files.

Uses Python's ast module (Abstract Syntax Tree — static analysis of source
code without importing or executing it) to extract:
    - top-level functions
    - methods defined directly on classes (not inherited)

For each symbol, extracts:
    - symbol name (qualified as ClassName.method_name for methods)
    - param names and count from the function signature
    - first non-empty line of the docstring as description
    - param types: left empty (no type annotations in target libraries)
    - returns: extracted from return annotation if present, else empty

This module is format-specific, not API-specific. It can be reused for any
untyped or partially-typed Python library.

Limitations:
    - Does not resolve inherited methods (use Sphinx XML for that)
    - Param types are empty unless the source uses PEP 484 annotations
    - 'self' and 'cls' params are excluded from the params list
"""

import ast
import logging
import os

log = logging.getLogger(__name__)

# Params to always exclude from the symbol's param list
_SKIP_PARAMS = {"self", "cls"}


def _extract_description(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Return the first non-empty line of the function's docstring, or ''."""
    docstring = ast.get_docstring(node)
    if not docstring:
        return ""
    for line in docstring.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def _extract_return_type(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Return the return annotation as a string, or '' if absent."""
    if node.returns is None:
        return ""
    try:
        return ast.unparse(node.returns)
    except Exception:
        return ""


def _build_params(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict]:
    """
    Build the params list from the function's argument nodes.
    Excludes self/cls. Types are extracted from annotations if present.
    """
    args      = node.args
    all_args  = args.posonlyargs + args.args + args.kwonlyargs
    if args.vararg:
        all_args.append(args.vararg)
    if args.kwarg:
        all_args.append(args.kwarg)

    params = []
    for arg in all_args:
        if arg.arg in _SKIP_PARAMS:
            continue
        param_type = ""
        if arg.annotation is not None:
            try:
                param_type = ast.unparse(arg.annotation)
            except Exception:
                pass
        params.append({
            "name":        arg.arg,
            "type":        param_type,
            "description": "",
        })
    return params


def _build_signature(symbol: str, params: list[dict]) -> str:
    """Reconstruct a readable signature string from symbol name and params."""
    param_str = ", ".join(
        f"{p['type']} {p['name']}".strip() if p["type"] else p["name"]
        for p in params
    )
    return f"{symbol}({param_str})"


def _parse_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    api: str,
    version: str,
    header: str,
    class_name: str = "",
) -> dict:
    """Parse a single function or method node into a symbol dict."""
    symbol      = f"{class_name}.{node.name}" if class_name else node.name
    params      = _build_params(node)
    return_type = _extract_return_type(node)
    description = _extract_description(node)
    signature   = _build_signature(symbol, params)

    return {
        "symbol":      symbol,
        "api":         api,
        "version":     version,
        "kind":        "function",
        "signature":   signature,
        "params":      params,
        "returns":     return_type,
        "header":      header,
        "description": description,
    }


def parse_file(path: str, api: str, version: str) -> list[dict]:
    """
    Parse a single Python source file into a list of symbol dicts.

    Extracts top-level functions and methods defined directly on classes.
    Does not recurse into nested functions.

    Args:
        path:    Absolute path to the .py file.
        api:     API name to embed in every symbol dict.
        version: Version string to embed in every symbol dict.

    Returns:
        List of symbol dicts conforming to the index schema.
    """
    header = os.path.basename(path)

    try:
        with open(path, "r", errors="replace") as f:
            source = f.read()
        tree = ast.parse(source, filename=path)
    except SyntaxError as e:
        log.warning("Syntax error parsing %s: %s", path, e)
        return []

    symbols = []

    for node in ast.iter_child_nodes(tree):
        # Top-level functions
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Skip private/dunder functions
            if not node.name.startswith("_"):
                symbols.append(_parse_function(node, api, version, header))

        # Class methods
        elif isinstance(node, ast.ClassDef):
            # Skip private classes
            if node.name.startswith("_"):
                continue
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Skip private/dunder methods except __init__
                    if child.name.startswith("_") and child.name != "__init__":
                        continue
                    symbols.append(
                        _parse_function(
                            child, api, version, header,
                            class_name=node.name,
                        )
                    )

    log.debug("Parsed %s: %d symbols", header, len(symbols))
    return symbols