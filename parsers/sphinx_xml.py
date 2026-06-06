"""
parsers/sphinx_xml.py

Format-specific parser for Sphinx XML builder output (sphinx-build -b xml).

Sphinx's XML builder emits Docutils-native XML — the internal document tree
after autodoc has resolved all imports and inheritance. This gives us the
full public API including inherited members, with param types resolved.

Relevant XML structure (per symbol):
    <desc domain="py" objtype="function|method|class">
        <desc_signature fullname="..." class="...">
            <desc_name>symbol_name</desc_name>
            <desc_parameterlist>
                <desc_parameter>
                    <desc_sig_name>param_name</desc_sig_name>
                    <desc_sig_operator>=</desc_sig_operator>   (if default)
                    ...
                </desc_parameter>
            </desc_parameterlist>
        </desc_signature>
        <desc_content>
            <paragraph>brief description</paragraph>
            <field_list>
                <field>
                    <field_name>Parameters</field_name>
                    <field_body>
                        <bullet_list>
                            <list_item>
                                <paragraph>
                                    <literal_strong>name</literal_strong>
                                    (<literal_emphasis>type</literal_emphasis>)
                                    – description
                                </paragraph>
                            </list_item>
                        </bullet_list>
                    </field_body>
                </field>
                <field>
                    <field_name>Return type</field_name>
                    <field_body><paragraph>type</paragraph></field_body>
                </field>
            </field_list>
        </desc_content>
    </desc>

This module is format-specific, not API-specific. It can be reused for any
library documented with Sphinx autodoc and built with sphinx-build -b xml.
"""

import logging
import os
import xml.etree.ElementTree as ET

log = logging.getLogger(__name__)

# Sphinx objtype values we extract. Others (module, attribute, property,
# exception, data) are skipped.
SUPPORTED_OBJTYPES = {"function", "method", "class"}

KIND_MAP = {
    "function": "function",
    "method":   "function",
    "class":    "struct",     # closest schema kind for a class definition
}


def _iter_text(element) -> str:
    """Concatenate all text content under an element, stripping whitespace."""
    return "".join(element.itertext()).strip()


def _parse_params_from_parameterlist(paramlist_elem) -> list[dict]:
    """
    Extract param names from <desc_parameterlist>.

    Types are not present in the parameter list element itself — they come
    from the <field_list> Parameters section. This function extracts names
    only; types are merged in _merge_param_types().
    """
    params = []
    if paramlist_elem is None:
        return params

    for param_elem in paramlist_elem.findall("desc_parameter"):
        # The param name is in <desc_sig_name> — skip operators and defaults
        name_elem = param_elem.find("desc_sig_name")
        if name_elem is None:
            continue
        name = (name_elem.text or "").strip()
        if name in ("self", "cls") or not name:
            continue
        params.append({"name": name, "type": "", "description": ""})

    return params


def _parse_field_list(content_elem) -> tuple[list[dict], str, str]:
    """
    Extract param types+descriptions, return type, and brief description
    from <desc_content>.

    Returns:
        param_info  list of {"name": str, "type": str, "description": str}
        return_type str
        description str  (first <paragraph> before <field_list>)
    """
    param_info  = []
    return_type = ""
    description = ""

    if content_elem is None:
        return param_info, return_type, description

    # First <paragraph> before any <field_list> is the brief description
    for child in content_elem:
        if child.tag == "paragraph":
            description = _iter_text(child)
            break
        if child.tag == "field_list":
            break

    field_list = content_elem.find("field_list")
    if field_list is None:
        return param_info, return_type, description

    for field in field_list.findall("field"):
        field_name_elem = field.find("field_name")
        if field_name_elem is None:
            continue
        field_name = (field_name_elem.text or "").strip()
        field_body = field.find("field_body")
        if field_body is None:
            continue

        if field_name == "Parameters":
            # Each <list_item> is one parameter
            for item in field_body.findall(".//list_item"):
                para = item.find("paragraph")
                if para is None:
                    continue

                name = ""
                ptype = ""
                pdesc = ""

                name_elem = para.find("literal_strong")
                if name_elem is not None:
                    name = (name_elem.text or "").strip()

                type_elem = para.find("literal_emphasis")
                if type_elem is None:
                    # Type may be wrapped in a <reference> inside the para
                    for ref in para.findall(".//literal_emphasis"):
                        ptype = _iter_text(ref)
                        break
                else:
                    ptype = _iter_text(type_elem)

                # Description is all text after the em-dash separator
                full_text = _iter_text(para)
                if "–" in full_text:
                    pdesc = full_text.split("–", 1)[1].strip()

                if name:
                    param_info.append({
                        "name":        name,
                        "type":        ptype,
                        "description": pdesc,
                    })

        elif field_name in ("Return type", "Returns"):
            return_type = _iter_text(field_body)

    return param_info, return_type, description


def _merge_param_types(
    params: list[dict],
    param_info: list[dict],
) -> list[dict]:
    """
    Merge type and description from field_list into the params list.

    Matches by name. If a param appears in field_list but not in the
    signature parameterlist (e.g. *args expanded), it is appended.
    """
    info_by_name = {p["name"]: p for p in param_info}

    merged = []
    seen   = set()
    for p in params:
        name = p["name"]
        seen.add(name)
        info = info_by_name.get(name, {})
        merged.append({
            "name":        name,
            "type":        info.get("type", ""),
            "description": info.get("description", ""),
        })

    # Append any params that appeared only in field_list (e.g. *args)
    for info in param_info:
        if info["name"] not in seen:
            merged.append(info)

    return merged


def _parse_desc(desc_elem, api: str, version: str, header: str) -> dict | None:
    """
    Parse a single <desc> element into a symbol dict.

    Returns None if the objtype is not in SUPPORTED_OBJTYPES.
    """
    objtype = desc_elem.get("objtype", "")
    if objtype not in SUPPORTED_OBJTYPES:
        return None

    sig_elem = desc_elem.find("desc_signature")
    if sig_elem is None:
        return None

    fullname = sig_elem.get("fullname", "").strip()
    if not fullname:
        return None

    # Use the last component as the symbol name, keep fullname for signature
    symbol = fullname

    paramlist_elem = sig_elem.find("desc_parameterlist")
    params         = _parse_params_from_parameterlist(paramlist_elem)

    content_elem                      = desc_elem.find("desc_content")
    param_info, return_type, description = _parse_field_list(content_elem)

    params    = _merge_param_types(params, param_info)
    signature = f"{symbol}({', '.join(p['name'] for p in params)})"

    return {
        "symbol":      symbol,
        "api":         api,
        "version":     version,
        "kind":        KIND_MAP[objtype],
        "signature":   signature,
        "params":      params,
        "returns":     return_type,
        "header":      header,
        "description": description,
    }


def _parse_xml_file(path: str, api: str, version: str) -> list[dict]:
    """Parse one Sphinx XML file, return list of symbol dicts."""
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        log.warning("Failed to parse %s: %s", path, e)
        return []

    header  = os.path.basename(path)
    symbols = []

    for desc_elem in tree.getroot().iter("desc"):
        if desc_elem.get("domain") != "py":
            continue
        symbol = _parse_desc(desc_elem, api, version, header)
        if symbol is not None:
            symbols.append(symbol)

    return symbols


def parse_xml_dir(xml_dir: str, api: str, version: str) -> list[dict]:
    """
    Parse all Sphinx XML files in xml_dir.

    Args:
        xml_dir:  Absolute path to sphinx-build -b xml output directory.
        api:      API name to embed in every symbol dict.
        version:  Version string to embed in every symbol dict.

    Returns:
        Deduplicated list of symbol dicts sorted by symbol name.
    """
    if not os.path.isdir(xml_dir):
        raise FileNotFoundError(f"Sphinx XML directory not found: {xml_dir}")

    all_symbols = []
    for fname in os.listdir(xml_dir):
        if not fname.endswith(".xml"):
            continue
        path    = os.path.join(xml_dir, fname)
        symbols = _parse_xml_file(path, api, version)
        all_symbols.extend(symbols)
        log.debug("Parsed %s: %d symbols", fname, len(symbols))

    # Deduplicate by symbol name
    seen   = set()
    unique = []
    for s in all_symbols:
        if s["symbol"] not in seen:
            seen.add(s["symbol"])
            unique.append(s)

    unique.sort(key=lambda s: s["symbol"])
    log.info("sphinx_xml: %d unique symbols from %s", len(unique), xml_dir)
    return unique