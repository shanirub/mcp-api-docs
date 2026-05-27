"""
ingest.py

Top-level ingestion orchestrator.

For each registered API:
  1. Calls the downloader to fetch raw docs and generate structured input.
  2. Calls the parser to extract symbol dicts.
  3. Writes the symbol list to index/<api>.json.

Usage:
    # Ingest all registered APIs:
    python ingest.py

    # Ingest a specific API only:
    python ingest.py freertos
"""

import json
import logging
import os
import sys

from config import INDEX_DIR
from downloaders import freertos as freertos_downloader
from parsers.freertos import FreeRTOSParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Registry: add a new entry here when adding a new API.
# Each entry:
#   downloader  module with a download() -> dict function
#   parser      BaseParser instance
#   index_key   key in download()'s return dict that points to the parser's source_dir
APIS = {
    "freertos": {
        "downloader": freertos_downloader,
        "parser":     FreeRTOSParser(),
        "index_key":  "xml_dir",
    },
}


def ingest_api(api_name: str) -> None:
    if api_name not in APIS:
        log.error("Unknown API: %s. Registered APIs: %s", api_name, list(APIS))
        sys.exit(1)

    entry = APIS[api_name]

    log.info("=== Ingesting %s ===", api_name)

    # Step 1: download
    result     = entry["downloader"].download()
    version    = result["version"]
    source_dir = result[entry["index_key"]]

    # Step 2: parse
    symbols = entry["parser"].parse(source_dir, version)

    if not symbols:
        log.warning("No symbols extracted for %s — index not written.", api_name)
        return

    # Step 3: write index
    os.makedirs(INDEX_DIR, exist_ok=True)
    index_path = os.path.join(INDEX_DIR, f"{api_name}.json")
    with open(index_path, "w") as f:
        json.dump(symbols, f, indent=2)

    log.info("Wrote %d symbols to %s", len(symbols), index_path)


def main() -> None:
    targets = sys.argv[1:] or list(APIS)
    for api_name in targets:
        ingest_api(api_name)
    log.info("Ingestion complete.")


if __name__ == "__main__":
    main()
