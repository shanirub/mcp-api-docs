"""
parsers/base.py

Abstract base class (ABC) for all doc parsers.

Every parser must implement parse(), which reads raw documentation from
a source directory and returns a list of symbol dicts conforming to the
shared index schema.

Index schema (per symbol):
{
    "symbol":      str,   # e.g. "xTaskCreate"
    "api":         str,   # e.g. "freertos"
    "version":     str,   # e.g. "V11.2.0"
    "kind":        str,   # "function" | "macro" | "typedef" | "enum" | "struct"
    "signature":   str,   # full signature string
    "params": [
        {
            "name":        str,
            "type":        str,
            "description": str,
        },
        ...
    ],
    "returns":     str,   # return type, empty string for void/macros
    "header":      str,   # e.g. "task.h"
}
"""

from abc import ABC, abstractmethod


class BaseParser(ABC):

    @abstractmethod
    def parse(self, source_dir: str, version: str) -> list[dict]:
        """
        Parse documentation from source_dir for the given version.

        Args:
            source_dir: Absolute path to the raw documentation source
                        (e.g. Doxygen XML directory, HTML directory, etc.)
            version:    Version string to embed in every symbol dict.

        Returns:
            List of symbol dicts conforming to the index schema above.
        """
        ...
