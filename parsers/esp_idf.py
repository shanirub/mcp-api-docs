"""
parsers/esp_idf.py

ESP-IDF component parser.

API-specific, not format-specific. Each component is a separate EspIdfParser
instance — the component name is passed at construction time and embedded in
every symbol dict via parse_xml_dir().

All XML parsing is delegated to parsers/doxygen.py, which is format-specific
and reusable across any Doxygen-based API.
"""

import logging

from parsers.base import BaseParser
from parsers.doxygen import parse_xml_dir

log = logging.getLogger(__name__)


class EspIdfParser(BaseParser):

    def __init__(self, component: str) -> None:
        """
        Args:
            component: ESP-IDF component name, e.g. "esp_driver_i2c".
                       Used as the api field in every symbol dict.
        """
        self.component = component

    def parse(self, source_dir: str, version: str) -> list[dict]:
        """
        Parse ESP-IDF component Doxygen XML into symbol dicts.

        Args:
            source_dir: Absolute path to the Doxygen XML output directory
                        for this component (e.g. docs/esp_idf/esp_driver_i2c/xml/).
            version:    Version string, e.g. "v6.0.1".

        Returns:
            List of symbol dicts conforming to the index schema.
        """
        log.info("Parsing ESP-IDF %s %s from %s", self.component, version, source_dir)
        symbols = parse_xml_dir(source_dir, self.component, version)
        log.info("ESP-IDF %s parser: %d symbols extracted", self.component, len(symbols))
        return symbols
