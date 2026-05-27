"""
parsers/freertos.py

FreeRTOS-specific parser.

This module is API-specific, not format-specific. It knows that FreeRTOS
uses Doxygen XML, delegates all XML parsing to parsers/doxygen.py, and
applies any FreeRTOS-specific post-processing (currently none needed).

If FreeRTOS ever changes its doc format, only this file needs updating —
parsers/doxygen.py remains reusable for other APIs.
"""

import logging

from parsers.base import BaseParser
from parsers.doxygen import parse_xml_dir

log = logging.getLogger(__name__)

API_NAME = "freertos"


class FreeRTOSParser(BaseParser):

    def parse(self, source_dir: str, version: str) -> list[dict]:
        """
        Parse FreeRTOS Doxygen XML into symbol dicts.

        Args:
            source_dir: Absolute path to the Doxygen XML output directory
                        (i.e. docs/freertos/xml/).
            version:    Version string, e.g. "V11.2.0".

        Returns:
            List of symbol dicts conforming to the index schema.
        """
        log.info("Parsing FreeRTOS %s from %s", version, source_dir)
        symbols = parse_xml_dir(source_dir, API_NAME, version)
        log.info("FreeRTOS parser: %d symbols extracted", len(symbols))
        return symbols
