"""
parsers/pigpio_python.py

pigpio Python API parser.

Delegates to parsers/python_docstring.py which uses ast-based static analysis
to extract symbols from Python source files.

pigpio.py defines its entire public API as methods on the pigpio.pi class,
plus a small number of module-level constants and callbacks. We parse the
single pigpio.py file directly.
"""

import logging
import os

from parsers.base import BaseParser
from parsers.python_docstring import parse_file

log = logging.getLogger(__name__)

API_NAME    = "pigpio_python"
SOURCE_FILE = "pigpio.py"


class PigpioPythonParser(BaseParser):

    def parse(self, source_dir: str, version: str) -> list[dict]:
        """
        Parse pigpio Python API into symbol dicts.

        Args:
            source_dir: Absolute path to the pigpio repo root
                        (i.e. docs/pigpio/source/).
                        pigpio.py is expected at source_dir/pigpio.py.
            version:    Version string, e.g. "v79".

        Returns:
            List of symbol dicts conforming to the index schema.
        """
        path = os.path.join(source_dir, SOURCE_FILE)
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"pigpio.py not found at expected path: {path}"
            )

        log.info("Parsing pigpio_python %s from %s", version, path)
        symbols = parse_file(path, API_NAME, version)
        log.info("pigpio_python parser: %d symbols extracted", len(symbols))
        return symbols