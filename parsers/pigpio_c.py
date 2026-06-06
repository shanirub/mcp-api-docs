"""
parsers/pigpio_c.py

pigpio C API parser.

Delegates to parsers/pigpio_text.py which handles the /*F*//*D...D*/ comment
style used in pigpio's C headers. No API-specific post-processing needed.
"""

import logging

from parsers.base import BaseParser
from parsers.pigpio_text import parse_source_dir

log = logging.getLogger(__name__)

API_NAME = "pigpio_c"


class PigpioCParser(BaseParser):

    def parse(self, source_dir: str, version: str) -> list[dict]:
        """
        Parse pigpio C headers into symbol dicts.

        Args:
            source_dir: Absolute path to the pigpio repo root
                        (i.e. docs/pigpio/source/).
            version:    Version string, e.g. "v79".

        Returns:
            List of symbol dicts conforming to the index schema.
        """
        log.info("Parsing pigpio_c %s from %s", version, source_dir)
        symbols = parse_source_dir(source_dir, API_NAME, version)
        log.info("pigpio_c parser: %d symbols extracted", len(symbols))
        return symbols