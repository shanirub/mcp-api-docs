"""
downloaders/freertos.py

Fetches the latest FreeRTOS-Kernel release from GitHub, performs a shallow
git clone (--depth 1) of the tagged commit, generates a minimal Doxyfile,
and runs Doxygen with GENERATE_XML=YES to produce structured XML output.

Output layout under DOCS_DIR:
    docs/
    └── freertos/
        ├── source/     shallow clone of FreeRTOS-Kernel at latest tag
        ├── doxyfile    generated minimal Doxygen config
        └── xml/        Doxygen XML output (parsed by parsers/doxygen.py)
"""

import json
import logging
import os
import shutil
import subprocess
import urllib.request

from config import DOCS_DIR

log = logging.getLogger(__name__)

GITHUB_API_LATEST = (
    "https://api.github.com/repos/FreeRTOS/FreeRTOS-Kernel/releases/latest"
)
REPO_URL = "https://github.com/FreeRTOS/FreeRTOS-Kernel.git"

# Minimal Doxyfile — only the settings we need.
# Doxygen fills everything else with sensible defaults.
DOXYFILE_TEMPLATE = """\
PROJECT_NAME     = FreeRTOS-Kernel
PROJECT_NUMBER   = {version}
INPUT            = {source_dir}/include
RECURSIVE        = YES
GENERATE_HTML    = NO
GENERATE_LATEX   = NO
GENERATE_XML     = YES
XML_OUTPUT       = {xml_dir}
QUIET            = YES
WARNINGS         = YES
"""


def _latest_version() -> str:
    """Query GitHub API for the latest FreeRTOS-Kernel release tag."""
    req = urllib.request.Request(
        GITHUB_API_LATEST,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "mcp-api-docs-server"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    tag = data["tag_name"]          # e.g. "V11.2.0"
    log.info("Latest FreeRTOS-Kernel release: %s", tag)
    return tag


def _clone(tag: str, source_dir: str) -> None:
    """Shallow-clone the kernel repo at the given tag into source_dir."""
    if os.path.exists(source_dir):
        log.info("Source dir exists, removing for fresh clone: %s", source_dir)
        shutil.rmtree(source_dir)

    log.info("Cloning FreeRTOS-Kernel %s ...", tag)
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", tag, REPO_URL, source_dir],
        check=True,
        capture_output=True,
        text=True,
    )
    log.info("Clone complete: %s", source_dir)


def _write_doxyfile(doxyfile_path: str, version: str,
                    source_dir: str, xml_dir: str) -> None:
    content = DOXYFILE_TEMPLATE.format(
        version=version,
        source_dir=source_dir,
        xml_dir=xml_dir,
    )
    with open(doxyfile_path, "w") as f:
        f.write(content)
    log.info("Doxyfile written: %s", doxyfile_path)


def _run_doxygen(doxyfile_path: str, xml_dir: str) -> None:
    if os.path.exists(xml_dir):
        log.info("Removing stale XML output: %s", xml_dir)
        shutil.rmtree(xml_dir)

    log.info("Running Doxygen ...")
    result = subprocess.run(
        ["doxygen", doxyfile_path],
        check=True,
        capture_output=True,
        text=True,
    )
    # Doxygen writes warnings to stderr even on success.
    # Log them at DEBUG so they don't pollute normal output.
    if result.stderr:
        for line in result.stderr.splitlines():
            log.debug("doxygen: %s", line)
    log.info("Doxygen XML written to: %s", xml_dir)


def download() -> dict:
    """
    Fetch latest FreeRTOS-Kernel docs and generate Doxygen XML.

    Returns a dict with keys:
        version    (str)  e.g. "V11.2.0"
        xml_dir    (str)  absolute path to the generated XML directory
    """
    out_dir     = os.path.join(DOCS_DIR, "freertos")
    source_dir  = os.path.join(out_dir, "source")
    xml_dir     = os.path.join(out_dir, "xml")
    doxyfile    = os.path.join(out_dir, "doxyfile")

    os.makedirs(out_dir, exist_ok=True)

    version = _latest_version()
    _clone(version, source_dir)
    _write_doxyfile(doxyfile, version, source_dir, xml_dir)
    _run_doxygen(doxyfile, xml_dir)

    return {"version": version, "xml_dir": xml_dir}
