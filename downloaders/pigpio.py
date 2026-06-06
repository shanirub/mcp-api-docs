"""
downloaders/pigpio.py

Fetches the latest pigpio release from GitHub via a shallow clone.
No Doxygen step — both pigpio_c and pigpio_python parsers work directly
from the source files.

Output layout under DOCS_DIR:
    docs/
    └── pigpio/
        └── source/     shallow clone of joan2937/pigpio at latest tag

Returns:
    version     (str)  e.g. "v79"
    source_dir  (str)  absolute path to the cloned repo root
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
    "https://api.github.com/repos/joan2937/pigpio/releases/latest"
)
REPO_URL = "https://github.com/joan2937/pigpio.git"


def _latest_version() -> str:
    """Query GitHub API for the latest pigpio release tag."""
    req = urllib.request.Request(
        GITHUB_API_LATEST,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "mcp-api-docs-server"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    tag = data["tag_name"]          # e.g. "v79"
    log.info("Latest pigpio release: %s", tag)
    return tag


def _clone(tag: str, source_dir: str) -> None:
    """Shallow-clone the pigpio repo at the given tag into source_dir."""
    if os.path.exists(source_dir):
        log.info("Source dir exists, removing for fresh clone: %s", source_dir)
        shutil.rmtree(source_dir)

    log.info("Cloning pigpio %s ...", tag)
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", tag, REPO_URL, source_dir],
        check=True,
        capture_output=True,
        text=True,
    )
    log.info("Clone complete: %s", source_dir)


def download() -> dict:
    """
    Fetch latest pigpio source.

    Returns a dict with keys:
        version     (str)  e.g. "v79"
        source_dir  (str)  absolute path to the cloned repo root
    """
    out_dir    = os.path.join(DOCS_DIR, "pigpio")
    source_dir = os.path.join(out_dir, "source")

    os.makedirs(out_dir, exist_ok=True)

    version = _latest_version()
    _clone(version, source_dir)

    return {"version": version, "source_dir": source_dir}