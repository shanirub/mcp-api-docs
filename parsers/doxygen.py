"""
parsers/doxygen.py

Shared Doxygen XML parser.

Doxygen's XML output consists of:
  - index.xml       master index listing all compounds (files, structs, etc.)
  - <refid>.xml     one file per compound with full member details

We only care about function and macro (define) members that have at least
a brief description — i.e. the documented public API surface.

This module is format-specific, not API-specific. It knows how to read
Doxygen XML but has no knowledge of FreeRTOS, ESP-IDF, or any other API.
API-specific logic (which members to include/exclude, how to normalise
names, etc.) belongs in the API-specific parser that calls this module.
"""

import logging
import os
import xml.etree.ElementTree as ET

log = logging.getLogger(__name__)

# Doxygen kinds we extract. Others (struct, class, file, namespace, etc.)
# are skipped — they're implementation details, not callable API symbols.
SUPPORTED_KINDS = {"function", "define"}

# Map Doxygen member kinds to our schema's "kind" field values.
KIND_MAP = {
    "function": "function",
    "define":   "macro",
}


def _text(element, tag: str, default: str = "") -> str:
    """Extract stripped text content from a child element, or return default."""
    child = element.find(tag)
    if child is None:
        return default
    # Doxygen wraps text in <para> inside description elements.
    # itertext() walks all nested tags and concatenates their text nodes.
    return " ".join((child.itertext())).strip() or default


def _parse_param(param_elem) -> dict:
    """Parse a single <param> element into our schema's param dict."""
    # <type> may contain nested tags (e.g. <ref> for cross-references).
    type_elem = param_elem.find("type")
    param_type = (
        "".join(type_elem.itertext()).strip() if type_elem is not None else ""
    )

    name_elem = param_elem.find("declname")
    param_name = name_elem.text.strip() if (name_elem is not None and name_elem.text) else ""

    desc_elem = param_elem.find("briefdescription")
    param_desc = (
        " ".join(desc_elem.itertext()).strip() if desc_elem is not None else ""
    )

    # Doxygen puts param descriptions inside <detaileddescription> ->
    # <parameterlist> -> <parameteritem>. That's handled at the member level
    # in _parse_member and merged in after this call.

    return {"name": param_name, "type": param_type, "description": param_desc}


def _extract_param_descriptions(detailed_elem) -> dict[str, str]:
    """
    Extract parameter descriptions from <detaileddescription>.

    Doxygen stores param docs separately from param declarations, inside:
      <detaileddescription>
        <para>
          <parameterlist kind="param">
            <parameteritem>
              <parameternamelist><parametername>name</parametername></parameternamelist>
              <parameterdescription><para>desc</para></parameterdescription>
            </parameteritem>
          </parameterlist>
        </para>
      </detaileddescription>

    Returns a dict mapping param name -> description string.
    """
    descriptions = {}
    if detailed_elem is None:
        return descriptions

    for item in detailed_elem.iter("parameteritem"):
        name_elem = item.find(".//parametername")
        desc_elem = item.find(".//parameterdescription")
        if name_elem is not None and name_elem.text:
            name = name_elem.text.strip()
            desc = (
                " ".join(desc_elem.itertext()).strip()
                if desc_elem is not None else ""
            )
            descriptions[name] = desc

    return descriptions


def _parse_member(member_elem, header: str, api: str, version: str) -> dict | None:
    """
    Parse a single <memberdef> element into a symbol dict.

    Returns None if the member should be skipped (undocumented, unsupported kind).
    """
    kind = member_elem.get("kind", "")
    if kind not in SUPPORTED_KINDS:
        return None

    brief = _text(member_elem, "briefdescription")
    if not brief:
        # Skip undocumented members — internal implementation details.
        return None

    symbol = _text(member_elem, "name")
    if not symbol:
        return None

    # Build full signature string.
    # For functions: "<return_type> <name>(<params>)"
    # For macros:    "<name>(<params>)" or just "<name>"
    return_type = "".join(
        (member_elem.find("type") or ET.Element("x")).itertext()
    ).strip()

    argsstring = _text(member_elem, "argsstring")   # e.g. "(TaskFunction_t pv, ...)"
    signature  = f"{return_type} {symbol}{argsstring}".strip()

    # Parse parameters from <param> elements.
    params = [_parse_param(p) for p in member_elem.findall("param")]

    # Merge in parameter descriptions from <detaileddescription>.
    detailed_elem = member_elem.find("detaileddescription")
    param_descs   = _extract_param_descriptions(detailed_elem)
    for p in params:
        if p["name"] in param_descs and not p["description"]:
            p["description"] = param_descs[p["name"]]

    # Extract return description from <detaileddescription> -> <simplesect kind="return">
    returns_desc = ""
    if detailed_elem is not None:
        for sect in detailed_elem.iter("simplesect"):
            if sect.get("kind") == "return":
                returns_desc = " ".join(sect.itertext()).strip()
                break

    return {
        "symbol":      symbol,
        "api":         api,
        "version":     version,
        "kind":        KIND_MAP[kind],
        "signature":   signature,
        "params":      params,
        "returns":     return_type,
        "header":      header,
        "description": brief,
    }


def _parse_compound_file(xml_path: str, api: str, version: str) -> list[dict]:
    """Parse one Doxygen compound XML file, return list of symbol dicts."""
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as e:
        log.warning("Failed to parse %s: %s", xml_path, e)
        return []

    root     = tree.getroot()
    symbols  = []

    for compound in root.findall(".//compounddef"):
        # compoundname gives us the header filename for file-level compounds.
        compound_name = _text(compound, "compoundname")
        # Strip path prefix — we only want e.g. "task.h" not "include/task.h"
        header = os.path.basename(compound_name)

        for member in compound.findall(".//memberdef"):
            symbol = _parse_member(member, header, api, version)
            if symbol is not None:
                symbols.append(symbol)

    return symbols


def parse_xml_dir(xml_dir: str, api: str, version: str) -> list[dict]:
    """
    Parse all compound XML files in xml_dir.

    Args:
        xml_dir:  Absolute path to Doxygen XML output directory.
        api:      API name to embed in every symbol dict (e.g. "freertos").
        version:  Version string to embed in every symbol dict.

    Returns:
        Deduplicated list of symbol dicts, sorted by symbol name.
    """
    index_path = os.path.join(xml_dir, "index.xml")
    if not os.path.exists(index_path):
        raise FileNotFoundError(f"Doxygen index not found: {index_path}")

    # Parse index.xml to get the list of compound refids.
    # This is more reliable than globbing *.xml (avoids re-parsing index.xml itself).
    index_tree = ET.parse(index_path)
    refids = [
        compound.get("refid")
        for compound in index_tree.getroot().findall("compound")
        if compound.get("refid")
    ]

    all_symbols = []
    for refid in refids:
        compound_path = os.path.join(xml_dir, f"{refid}.xml")
        if not os.path.exists(compound_path):
            log.warning("Compound file missing: %s", compound_path)
            continue
        symbols = _parse_compound_file(compound_path, api, version)
        all_symbols.extend(symbols)
        log.debug("Parsed %s: %d symbols", refid, len(symbols))

    # Deduplicate by symbol name — Doxygen sometimes emits the same symbol
    # from both a .h and a .c compound.
    seen    = set()
    unique  = []
    for s in all_symbols:
        if s["symbol"] not in seen:
            seen.add(s["symbol"])
            unique.append(s)

    unique.sort(key=lambda s: s["symbol"])
    log.info("Parsed %d unique symbols from %s", len(unique), xml_dir)
    return unique
