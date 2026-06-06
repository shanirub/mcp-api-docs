"""
downloaders/luma_oled.py

Fetches the latest luma.oled release from GitHub, creates an isolated venv,
installs luma.oled + luma.core + sphinx dependencies, and runs sphinx-build
with the XML builder to produce structured Docutils XML output.

The XML builder resolves inherited members at build time (via live import),
giving us the full public API including methods inherited from luma.core.

Output layout under DOCS_DIR:
    docs/
    └── luma_oled/
        ├── source/     shallow clone of rm-hull/luma.oled at latest tag
        ├── venv/       isolated Python venv for sphinx build
        └── xml/        sphinx-build -b xml output (parsed by parsers/sphinx_xml.py)

Returns:
    version  (str)  e.g. "3.15.0"
    xml_dir  (str)  absolute path to the sphinx XML output directory
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import urllib.request

from config import DOCS_DIR

log = logging.getLogger(__name__)

GITHUB_API_TAGS = (
    "https://api.github.com/repos/rm-hull/luma.oled/tags?per_page=1"
)
REPO_URL = "https://github.com/rm-hull/luma.oled.git"

# Packages installed into the build venv.
# sphinx-rtd-theme is required by doc/conf.py (html_theme = 'sphinx_rtd_theme').
# Even though we use the xml builder it must be importable or conf.py errors.
VENV_PACKAGES = [
    "luma.oled",
    "luma.core",
    "sphinx",
    "sphinx-rtd-theme",
]


def _latest_version() -> str:
    """Query GitHub API for the latest luma.oled release tag."""
    req = urllib.request.Request(
        GITHUB_API_TAGS,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "mcp-api-docs-server"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    tag = data[0]["name"]      # e.g. "3.15.0"
    log.info("Latest luma.oled release: %s", tag)
    return tag


def _clone(tag: str, source_dir: str) -> None:
    """Shallow-clone luma.oled at the given tag into source_dir."""
    if os.path.exists(source_dir):
        log.info("Source dir exists, removing for fresh clone: %s", source_dir)
        shutil.rmtree(source_dir)

    log.info("Cloning luma.oled %s ...", tag)
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", tag, REPO_URL, source_dir],
        check=True,
        capture_output=True,
        text=True,
    )
    log.info("Clone complete: %s", source_dir)


def _create_venv(venv_dir: str) -> str:
    """
    Create an isolated venv and return the path to its python executable.
    Recreates from scratch on every run to ensure a clean environment.
    """
    if os.path.exists(venv_dir):
        log.info("Removing stale venv: %s", venv_dir)
        shutil.rmtree(venv_dir)

    log.info("Creating venv: %s", venv_dir)
    subprocess.run(
        [sys.executable, "-m", "venv", venv_dir],
        check=True,
        capture_output=True,
        text=True,
    )
    return os.path.join(venv_dir, "bin", "python")


def _install_packages(python: str) -> None:
    """Install required packages into the venv."""
    log.info("Installing packages into venv: %s", VENV_PACKAGES)
    subprocess.run(
        [python, "-m", "pip", "install", "--quiet"] + VENV_PACKAGES,
        check=True,
        capture_output=True,
        text=True,
    )
    log.info("Package installation complete.")


def _run_sphinx(python: str, doc_dir: str, xml_dir: str) -> None:
    """Run sphinx-build -b xml using the venv's sphinx installation."""
    if os.path.exists(xml_dir):
        log.info("Removing stale XML output: %s", xml_dir)
        shutil.rmtree(xml_dir)

    sphinx_build = os.path.join(os.path.dirname(python), "sphinx-build")
    log.info("Running sphinx-build -b xml ...")
    result = subprocess.run(
        [sphinx_build, "-b", "xml", doc_dir, xml_dir],
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stderr:
        for line in result.stderr.splitlines():
            log.debug("sphinx: %s", line)
    log.info("Sphinx XML written to: %s", xml_dir)


def download() -> dict:
    """
    Fetch latest luma.oled docs and generate Sphinx XML.

    Returns a dict with keys:
        version  (str)  e.g. "3.15.0"
        xml_dir  (str)  absolute path to the Sphinx XML output directory
    """
    out_dir    = os.path.join(DOCS_DIR, "luma_oled")
    source_dir = os.path.join(out_dir, "source")
    venv_dir   = os.path.join(out_dir, "venv")
    xml_dir    = os.path.join(out_dir, "xml")
    doc_dir    = os.path.join(source_dir, "doc")

    os.makedirs(out_dir, exist_ok=True)

    version = _latest_version()
    _clone(version, source_dir)
    python = _create_venv(venv_dir)
    _install_packages(python)
    _run_sphinx(python, doc_dir, xml_dir)

    return {"version": version, "xml_dir": xml_dir}