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

pigpio is handled separately because pigpio_c and pigpio_python share one
downloader — the repo is cloned once and both parsers read from the same
source_dir. Only one of the download calls is active at a time; the other
is commented out to avoid cloning twice during normal single-API runs.

Usage:
    # Ingest all registered APIs (including all ESP-IDF components):
    python ingest.py

    # Ingest a specific API only:
    python ingest.py freertos

    # Ingest all ESP-IDF components:
    python ingest.py esp_idf

    # Ingest a specific ESP-IDF component:
    python ingest.py esp_driver_i2c

    # Ingest both pigpio APIs (single clone):
    python ingest.py pigpio

    # Ingest luma.oled:
    python ingest.py luma_oled
"""

import json
import logging
import os
import sys

from config import INDEX_DIR, ESP_IDF_COMPONENTS
from downloaders import freertos as freertos_downloader
from downloaders import esp_idf as esp_idf_downloader
from downloaders import pigpio as pigpio_downloader
from downloaders import luma_oled as luma_oled_downloader
from parsers.freertos import FreeRTOSParser
from parsers.esp_idf import EspIdfParser
from parsers.pigpio_c import PigpioCParser
from parsers.pigpio_python import PigpioPythonParser
from parsers.luma_oled import LumaOledParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# Single-API registry — each entry has one downloader and one parser.
# download() returns a dict with "version" and a path key.
APIS = {
    "freertos": {
        "downloader": freertos_downloader,
        "parser":     FreeRTOSParser(),
        "index_key":  "xml_dir",
    },
    "luma_oled": {
        "downloader": luma_oled_downloader,
        "parser":     LumaOledParser(),
        "index_key":  "xml_dir",
    },
}

# ESP-IDF component registry — keyed by component name.
ESP_IDF_APIS = {
    component: EspIdfParser(component)
    for component in ESP_IDF_COMPONENTS
}

# pigpio parsers — instantiated here, used in ingest_pigpio()
_PIGPIO_PARSERS = {
    "pigpio_c":     PigpioCParser(),
    "pigpio_python": PigpioPythonParser(),
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


def ingest_pigpio() -> None:
    """
    Ingest pigpio_c and pigpio_python from a single clone.

    The repo is cloned once by pigpio_downloader.download(). Both parsers
    then read from the same source_dir. This avoids cloning the repo twice.

    To ingest only one of the two APIs, comment out the unwanted parser call
    below — do NOT call pigpio_downloader.download() twice.
    """
    log.info("=== Ingesting pigpio ===")
    result     = pigpio_downloader.download()
    version    = result["version"]
    source_dir = result["source_dir"]

    for api_name, parser in _PIGPIO_PARSERS.items():
        symbols = parser.parse(source_dir, version)
        _write_index(api_name, symbols)

        # To skip one API, comment out its entry in _PIGPIO_PARSERS above
        # or comment out the relevant line here:
        #   "pigpio_c":     PigpioCParser(),      # comment to skip C API
        #   "pigpio_python": PigpioPythonParser(), # comment to skip Python API


def ingest_esp_idf(component_filter: str | None = None) -> None:
    """
    Ingest ESP-IDF components.

    Args:
        component_filter: If given, ingest only this component.
                          If None, ingest all components in ESP_IDF_APIS.
    """
    log.info("=== Ingesting ESP-IDF ===")

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
            ingest_pigpio()
            ingest_esp_idf()
        elif target == "pigpio":
            ingest_pigpio()
        elif target == "esp_idf":
            ingest_esp_idf()
        elif target in ESP_IDF_APIS:
            ingest_esp_idf(component_filter=target)
        elif target in APIS:
            ingest_single(target)
        else:
            log.error(
                "Unknown target: %s. Known: %s, pigpio, esp_idf, %s",
                target,
                list(APIS),
                list(ESP_IDF_APIS),
            )
            sys.exit(1)

    log.info("Ingestion complete.")


if __name__ == "__main__":
    main()