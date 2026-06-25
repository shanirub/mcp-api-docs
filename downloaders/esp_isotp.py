"""
downloaders/esp_isotp.py

Fetches the esp_isotp component from espressif/idf-extra-components and its
vendored isotp-c submodule (github.com/SimonCahill/isotp-c), then runs Doxygen
TWICE — once per namespace — to produce two independent XML directories.

Why this is a separate downloader (not an ESP_IDF_COMPONENTS entry):
  - Different repo. esp_isotp does NOT exist in espressif/esp-idf; it lives in
    idf-extra-components, which your esp_idf downloader never clones.
  - Different header-dir convention. Public headers are under inc/ (not include/),
    so _sparse_paths()'s parts.index("include") assumption does not apply.
  - Two API namespaces from one clone. The ESP wrapper (esp_isotp_*) and the
    underlying protocol lib (isotp_*) are distinct surfaces. This mirrors the
    pigpio pattern (one clone, two parsers, two indexes), not the esp_idf one.

Versioning:
  idf-extra-components publishes NO git tags, so there is nothing to pin to a
  release — we track master HEAD. master moves between ingests, so we stamp the
  superproject's short commit SHA into the esp_isotp version string to record
  exactly what was built. For reproducible builds, replace MASTER_REF below with
  a specific commit SHA.

Output layout under DOCS_DIR:
    docs/
    └── esp_isotp/
        ├── source/                 sparse checkout of idf-extra-components (master)
        │   └── esp_isotp/
        │       ├── inc/esp_isotp.h
        │       └── isotp-c/        (submodule, populated at the pinned SHA)
        ├── esp_isotp/
        │   ├── doxyfile
        │   └── xml/
        └── isotp_c/
            ├── doxyfile
            └── xml/
"""

import logging
import os
import re
import shutil
import subprocess

from config import DOCS_DIR

log = logging.getLogger(__name__)

REPO_URL  = "https://github.com/espressif/idf-extra-components.git"
# Track master HEAD. For a reproducible build, set this to a commit SHA instead,
# e.g. MASTER_REF = "1a2b3c4..." — the rest of the pipeline is unchanged.
MASTER_REF = "master"

# Sparse-checkout the component dir only (cone mode also materialises root files
# such as .gitmodules, which submodule update needs).
COMPONENT_PATH = "esp_isotp"
SUBMODULE_PATH = "esp_isotp/isotp-c"   # relative to the checkout root

# Per-namespace Doxygen inputs: api name -> header dir relative to source root.
#   esp_isotp -> inc/   (esp_isotp.h, the TWAI-backed wrapper API)
#   isotp_c   -> isotp-c/ (isotp.h + friends, the protocol library)
NAMESPACES = {
    "esp_isotp": "esp_isotp/inc",
    "isotp_c":   "esp_isotp/isotp-c",
}

# FILE_PATTERNS = *.h is the key difference from the esp_idf template: isotp-c/
# is a flat dir mixing isotp.h and isotp.c, and we must not parse the .c file.
DOXYFILE_TEMPLATE = """\
PROJECT_NAME        = {api}
PROJECT_NUMBER      = {version}
INPUT               = {input_dir}
FILE_PATTERNS       = *.h
RECURSIVE           = YES
EXCLUDE_PATTERNS    = */private_include/* */test/* */examples/*
GENERATE_HTML       = NO
GENERATE_LATEX      = NO
GENERATE_XML        = YES
XML_OUTPUT          = {xml_dir}
XML_PROGRAMLISTING  = NO
EXTRACT_ALL         = YES
QUIET               = YES
WARNINGS            = YES

ENABLE_PREPROCESSING   = YES
MACRO_EXPANSION        = YES
EXPAND_ONLY_PREDEF     = YES
SEARCH_INCLUDES        = YES
SKIP_FUNCTION_MACROS   = NO
INCLUDE_PATH           = {input_dir}

PREDEFINED             = \
    "__attribute__(x)=" \
    "__deprecated=" \
    "IRAM_ATTR=" \
    "ESP_EARLY_INIT_ATTRIBUTE="
"""


def _run(cmd: list[str], cwd: str, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=capture, text=True)


def _sparse_clone(source_dir: str) -> None:
    """
    Sparse-clone idf-extra-components at MASTER_REF, fetching only esp_isotp/,
    then init + update the isotp-c submodule at its pinned commit.
    """
    if os.path.exists(source_dir):
        log.info("Removing existing source dir: %s", source_dir)
        shutil.rmtree(source_dir)
    os.makedirs(source_dir, exist_ok=True)

    _run(["git", "init"], source_dir)
    _run(["git", "remote", "add", "origin", REPO_URL], source_dir)
    _run(["git", "sparse-checkout", "init", "--cone"], source_dir)
    _run(["git", "sparse-checkout", "set", COMPONENT_PATH], source_dir)

    log.info("Fetching idf-extra-components @ %s (sparse, depth=1) ...", MASTER_REF)
    # check=True, capture=False so clone progress is visible, matching esp_idf.
    _run(["git", "fetch", "--depth", "1", "origin", MASTER_REF], source_dir, capture=False)
    _run(["git", "checkout", "FETCH_HEAD"], source_dir)
    log.info("Sparse checkout complete: %s", source_dir)

    # Populate the isotp-c submodule at the SHA esp_isotp pins. No --depth here:
    # fetching an arbitrary pinned commit shallowly is unreliable across servers.
    log.info("Initialising submodule %s ...", SUBMODULE_PATH)
    _run(["git", "submodule", "update", "--init", SUBMODULE_PATH], source_dir, capture=False)

    # FAIL LOUD if the submodule did not populate. A silent skip here is exactly
    # the failure mode that masks "zero symbols indexed" downstream.
    isotp_header = os.path.join(source_dir, SUBMODULE_PATH, "isotp.h")
    if not os.path.isfile(isotp_header):
        raise RuntimeError(
            f"isotp-c submodule did not populate: {isotp_header} missing. "
            "Check network access to github.com/SimonCahill/isotp-c and that "
            ".gitmodules was checked out at the repo root."
        )
    log.info("Submodule populated: %s", isotp_header)


def _esp_isotp_version(source_dir: str) -> str:
    """
    Build the esp_isotp version string: the declared component version from
    idf_component.yml, stamped with the superproject's short SHA (since we
    track a moving master). Parsed with a regex to avoid a PyYAML dependency.
    """
    yml = os.path.join(source_dir, COMPONENT_PATH, "idf_component.yml")
    declared = "unknown"
    try:
        with open(yml) as f:
            for line in f:
                m = re.match(r'\s*version:\s*["\']?([^"\'\s]+)', line)
                if m:
                    declared = m.group(1)
                    break
    except FileNotFoundError:
        log.warning("idf_component.yml not found: %s", yml)

    short = _run(["git", "rev-parse", "--short", "HEAD"], source_dir).stdout.strip()
    return f"{declared}+g{short}"   # e.g. "0.1.1+g1a2b3c4"


def _isotp_c_version(source_dir: str) -> str:
    """isotp_c's honest version is the pinned submodule commit it ships at."""
    sub = os.path.join(source_dir, SUBMODULE_PATH)
    short = _run(["git", "rev-parse", "--short", "HEAD"], sub).stdout.strip()
    return f"isotp-c@{short}"


def _write_doxyfile(path: str, api: str, version: str,
                    input_dir: str, xml_dir: str) -> None:
    with open(path, "w") as f:
        f.write(DOXYFILE_TEMPLATE.format(
            api=api, version=version, input_dir=input_dir, xml_dir=xml_dir,
        ))
    log.info("Doxyfile written: %s", path)


def _run_doxygen(doxyfile_path: str, xml_dir: str) -> None:
    if os.path.exists(xml_dir):
        shutil.rmtree(xml_dir)
    result = subprocess.run(
        ["doxygen", doxyfile_path], check=True, capture_output=True, text=True,
    )
    for line in result.stderr.splitlines():
        log.debug("doxygen: %s", line)
    log.info("Doxygen XML written to: %s", xml_dir)


def download() -> dict[str, dict]:
    """
    Fetch esp_isotp + isotp-c and generate one Doxygen XML dir per namespace.

    Returns (same shape ingest.py expects, keyed by api name):
        {
            "esp_isotp": {"version": "0.1.1+g<sha>",  "xml_dir": "/.../esp_isotp/xml"},
            "isotp_c":   {"version": "isotp-c@<sha>",  "xml_dir": "/.../isotp_c/xml"},
        }
    """
    out_dir    = os.path.join(DOCS_DIR, "esp_isotp")
    source_dir = os.path.join(out_dir, "source")
    os.makedirs(out_dir, exist_ok=True)

    _sparse_clone(source_dir)

    versions = {
        "esp_isotp": _esp_isotp_version(source_dir),
        "isotp_c":   _isotp_c_version(source_dir),
    }

    results = {}
    for api, input_subpath in NAMESPACES.items():
        api_dir   = os.path.join(out_dir, api)
        xml_dir   = os.path.join(api_dir, "xml")
        doxyfile  = os.path.join(api_dir, "doxyfile")
        input_dir = os.path.join(source_dir, input_subpath)
        os.makedirs(api_dir, exist_ok=True)

        # Fail loud rather than silently skip (the lesson from the esp_idf path).
        if not os.path.isdir(input_dir):
            raise RuntimeError(f"Input dir missing for {api}: {input_dir}")

        _write_doxyfile(doxyfile, api, versions[api], input_dir, xml_dir)
        _run_doxygen(doxyfile, xml_dir)

        results[api] = {"version": versions[api], "xml_dir": xml_dir}
        n = len(os.listdir(xml_dir)) if os.path.isdir(xml_dir) else 0
        log.info("Namespace %s done: %d XML files", api, n)

    return results