"""
downloaders/esp_idf.py

Fetches the latest ESP-IDF release from GitHub using a sparse checkout —
fetching only the component include directories listed in ESP_IDF_COMPONENTS —
generates one Doxyfile per component, and runs Doxygen to produce one XML
directory per component.

Output layout under DOCS_DIR:
    docs/
    └── esp_idf/
        ├── source/                  sparse checkout of esp-idf at latest tag
        ├── esp_driver_i2c/
        │   ├── doxyfile
        │   └── xml/
        ├── esp_wifi/
        │   ├── doxyfile
        │   └── xml/
        └── ...
"""

import json
import logging
import os
import shutil
import subprocess
import urllib.request

from config import DOCS_DIR, ESP_IDF_COMPONENTS

log = logging.getLogger(__name__)

GITHUB_API_LATEST = (
    "https://api.github.com/repos/espressif/esp-idf/releases/latest"
)
REPO_URL = "https://github.com/espressif/esp-idf.git"

# Sparse checkout paths — one per component, derived from ESP_IDF_COMPONENTS.
# We fetch the parent include/ dir (one level up from the input_subpath)
# to ensure git includes the directory itself.
def _sparse_paths() -> list[str]:
    paths = set()
    for subpath in ESP_IDF_COMPONENTS.values():
        # e.g. "components/esp_driver_i2c/include/driver" →
        #      "components/esp_driver_i2c/include"
        parts = subpath.split("/")
        include_idx = parts.index("include")
        paths.add("/".join(parts[:include_idx + 1]))
    return sorted(paths)


DOXYFILE_TEMPLATE = """\
PROJECT_NAME        = {component}
PROJECT_NUMBER      = {version}
INPUT               = {input_dir}
RECURSIVE           = YES
EXCLUDE_PATTERNS    = */esp_private/* */local/* */private_include/*
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
    "SOC_I2C_SUPPORT_SLAVE=1" \
    "SOC_I2C_SUPPORT_10BIT_ADDR=1" \
    "CONFIG_SOC_I2C_SUPPORT_SLAVE=1" \
    "SOC_UART_SUPPORT_WAKEUP_INT=1" \
    "SOC_UART_SUPPORT_FSM_TX_WAIT_SEND=1" \ 
    "SOC_RTCIO_PIN_COUNT=1" \
    "CONFIG_ESP_WIFI_ENABLED=1" \
    "CONFIG_ESP_WIFI_SOFTAP_SUPPORT=1" \
    "ESP_IDF_VERSION_MAJOR=6" \
    "ESP_IDF_VERSION_MINOR=0" \
    "__attribute__(x)=" \
    "__deprecated=" \
    "IRAM_ATTR=" \
    "ESP_EARLY_INIT_ATTRIBUTE="
"""


def _latest_version() -> str:
    req = urllib.request.Request(
        GITHUB_API_LATEST,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "mcp-api-docs-server",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    tag = data["tag_name"]
    log.info("Latest ESP-IDF release: %s", tag)
    return tag


def _sparse_clone(tag: str, source_dir: str) -> None:
    """
    Sparse-clone ESP-IDF at the given tag, fetching only the include
    directories for the components in ESP_IDF_COMPONENTS.
    """
    if os.path.exists(source_dir):
        log.info("Removing existing source dir: %s", source_dir)
        shutil.rmtree(source_dir)

    os.makedirs(source_dir, exist_ok=True)

    paths = _sparse_paths()
    log.info("Sparse paths: %s", paths)

    subprocess.run(["git", "init"],
                   cwd=source_dir, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", REPO_URL],
                   cwd=source_dir, check=True, capture_output=True)
    subprocess.run(["git", "sparse-checkout", "init", "--cone"],
                   cwd=source_dir, check=True, capture_output=True)
    subprocess.run(["git", "sparse-checkout", "set"] + paths,
                   cwd=source_dir, check=True, capture_output=True)

    log.info("Fetching ESP-IDF %s (sparse, depth=1) — this may take a minute ...", tag)
    subprocess.run(
        ["git", "fetch", "--depth", "1", "origin", f"refs/tags/{tag}"],
        cwd=source_dir, check=True,
    )
    subprocess.run(
        ["git", "checkout", "FETCH_HEAD"],
        cwd=source_dir, check=True, capture_output=True,
    )
    log.info("Sparse checkout complete: %s", source_dir)


def _write_doxyfile(path: str, component: str, version: str,
                    input_dir: str, xml_dir: str) -> None:
    with open(path, "w") as f:
        f.write(DOXYFILE_TEMPLATE.format(
            component=component,
            version=version,
            input_dir=input_dir,
            xml_dir=xml_dir,
        ))
    log.info("Doxyfile written: %s", path)


def _run_doxygen(doxyfile_path: str, xml_dir: str) -> None:
    if os.path.exists(xml_dir):
        shutil.rmtree(xml_dir)
    result = subprocess.run(
        ["doxygen", doxyfile_path],
        check=True, capture_output=True, text=True,
    )
    if result.stderr:
        for line in result.stderr.splitlines():
            log.debug("doxygen: %s", line)
    log.info("Doxygen XML written to: %s", xml_dir)


def download() -> dict[str, dict]:
    """
    Fetch latest ESP-IDF and generate Doxygen XML for all components.

    Returns a dict keyed by component name:
        {
            "esp_driver_i2c": {"version": "v6.0.1", "xml_dir": "/path/to/xml"},
            ...
        }
    """
    out_dir    = os.path.join(DOCS_DIR, "esp_idf")
    source_dir = os.path.join(out_dir, "source")

    os.makedirs(out_dir, exist_ok=True)

    version = _latest_version()
    _sparse_clone(version, source_dir)

    results = {}
    for component, input_subpath in ESP_IDF_COMPONENTS.items():
        comp_dir  = os.path.join(out_dir, component)
        xml_dir   = os.path.join(comp_dir, "xml")
        doxyfile  = os.path.join(comp_dir, "doxyfile")
        input_dir = os.path.join(source_dir, input_subpath)

        os.makedirs(comp_dir, exist_ok=True)

        if not os.path.isdir(input_dir):
            log.warning("Input dir missing for %s: %s — skipping", component, input_dir)
            continue

        _write_doxyfile(doxyfile, component, version, input_dir, xml_dir)
        _run_doxygen(doxyfile, xml_dir)

        results[component] = {"version": version, "xml_dir": xml_dir}
        log.info("Component %s done: %d XML files", component,
                 len(os.listdir(xml_dir)) if os.path.isdir(xml_dir) else 0)

    return results
