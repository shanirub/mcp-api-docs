"""
parsers/luma_oled.py

luma.oled API parser.

Delegates to parsers/sphinx_xml.py which parses Sphinx XML builder output.
The XML is produced by downloaders/luma_oled.py using sphinx-build -b xml,
which resolves all inherited members from luma.core at build time.
"""

import logging

from parsers.base import BaseParser
from parsers.sphinx_xml import parse_xml_dir

log = logging.getLogger(__name__)

API_NAME = "luma_oled"


class LumaOledParser(BaseParser):

    def parse(self, source_dir: str, version: str) -> list[dict]:
        """
        Parse luma.oled Sphinx XML into symbol dicts.

        Args:
            source_dir: Absolute path to the sphinx-build -b xml output
                        directory (i.e. docs/luma_oled/xml/).
            version:    Version string, e.g. "3.15.0".

        Returns:
            List of symbol dicts conforming to the index schema.
        """
        log.info("Parsing luma_oled %s from %s", version, source_dir)
        symbols = parse_xml_dir(source_dir, API_NAME, version)
        log.info("luma_oled parser: %d symbols extracted", len(symbols))
        return symbols