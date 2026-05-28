"""
ingest.py

Top-level ingestion orchestrator.

For each registered API:
  1. Calls the downloader to fetch raw docs and generate structured input.
  2. Calls the parser to extract symbol dicts.
  3. Writes the symbol list to index/<api>.json.

ESP-IDF is handled separately from single-API entries: one download() call
fetches all components via sparse checkout, then each component is parsed
and written to its own index file.

Usage:
    # Ingest all registered APIs (including all ESP-IDF components):
    python ingest.py

    # Ingest a specific API only:
    python ingest.py freertos

    # Ingest all ESP-IDF components:
    python ingest.py esp_idf

    # Ingest a specific ESP-IDF component:
    python ingest.py esp_driver_i2c
"""

import json
import logging
import os
import sys

from config import INDEX_DIR, ESP_IDF_COMPONENTS
from downloaders import freertos as freertos_downloader
from downloaders import esp_idf as esp_idf_downloader
from parsers.freertos import FreeRTOSParser
from parsers.esp_idf import EspIdfParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# Single-API registry — each entry has one downloader and one parser.
# download() returns a dict with "version" and "xml_dir".
APIS = {
    "freertos": {
        "downloader": freertos_downloader,
        "parser":     FreeRTOSParser(),
        "index_key":  "xml_dir",
    },
}

# ESP-IDF component registry — keyed by component name.
# Parsers are instantiated once per component.
ESP_IDF_APIS = {
    component: EspIdfParser(component)
    for component in ESP_IDF_COMPONENTS
}


def _write_index(api_name: str, symbols: list[dict]) -> None:
    """Write symbol list to index/<api_name>.json."""
    if not symbols:
        log.warning("No symbols extracted for %s — index not written.", api_name)
        return
    os.makedirs(INDEX_DIR, exist_ok=True)
    index_path = os.path.join(INDEX_DIR, f"{api_name}.json")
    with open(index_path, "w") as f:
        json.dump(symbols, f, indent=2)
    log.info("Wrote %d symbols to %s", len(symbols), index_path)


def ingest_single(api_name: str) -> None:
    """Ingest one entry from the APIS registry."""
    entry      = APIS[api_name]
    log.info("=== Ingesting %s ===", api_name)
    result     = entry["downloader"].download()
    version    = result["version"]
    source_dir = result[entry["index_key"]]
    symbols    = entry["parser"].parse(source_dir, version)
    _write_index(api_name, symbols)


def ingest_esp_idf(component_filter: str | None = None) -> None:
    """
    Ingest ESP-IDF components.

    Args:
        component_filter: If given, ingest only this component.
                          If None, ingest all components in ESP_IDF_APIS.
    """
    log.info("=== Ingesting ESP-IDF ===")

    # Always run the full download — sparse checkout fetches all components
    # in one git operation, which is more efficient than per-component fetches.
    results = esp_idf_downloader.download()

    targets = (
        {component_filter: ESP_IDF_APIS[component_filter]}
        if component_filter
        else ESP_IDF_APIS
    )

    for component, parser in targets.items():
        if component not in results:
            log.warning("No download result for %s — skipping.", component)
            continue
        version    = results[component]["version"]
        xml_dir    = results[component]["xml_dir"]
        symbols    = parser.parse(xml_dir, version)
        _write_index(component, symbols)


def main() -> None:
    targets = sys.argv[1:] or ["all"]

    for target in targets:
        if target == "all":
            for api_name in APIS:
                ingest_single(api_name)
            ingest_esp_idf()
        elif target == "esp_idf":
            ingest_esp_idf()
        elif target in ESP_IDF_APIS:
            ingest_esp_idf(component_filter=target)
        elif target in APIS:
            ingest_single(target)
        else:
            log.error(
                "Unknown target: %s. Known: %s, esp_idf, %s",
                target,
                list(APIS),
                list(ESP_IDF_APIS),
            )
            sys.exit(1)

    log.info("Ingestion complete.")


if __name__ == "__main__":
    main()
