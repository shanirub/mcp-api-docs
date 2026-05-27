# How to add a new API parser

This document describes the steps to add support for a new API to the index.

---

## 1. Add a downloader

Create `downloaders/<api>.py`. It must expose a `download()` function that:
- Fetches the raw documentation for the API (clone, wget, etc.)
- Produces a structured output under `docs/<api>/`
- Returns a dict with at minimum:
  - `version` (str) — the version string to embed in every symbol
  - a path key pointing to the parsed input for the parser (e.g. `xml_dir`)

If the API uses Doxygen, follow `downloaders/freertos.py` as a template —
generate a minimal Doxyfile and run `doxygen` to produce XML output.

If the API uses a different format, produce whatever output your parser needs
and document the expected layout in your parser module's docstring.

---

## 2. Add a parser

Create `parsers/<api>.py`. It must:
- Subclass `BaseParser` from `parsers/base.py`
- Implement `parse(source_dir: str, version: str) -> list[dict]`
- Return symbol dicts conforming to the index schema (see `parsers/base.py`)

If the API uses Doxygen XML, delegate to `parsers/doxygen.parse_xml_dir()`
and apply any API-specific post-processing after. See `parsers/freertos.py`.

If the API uses a different format, write a new format-specific parser module
(e.g. `parsers/sphinx.py`) and have your API parser call it — mirroring the
doxygen.py / freertos.py split.

---

## 3. Register in ingest.py

Add a new entry to the `APIS` dict in `ingest.py`:

```python
from downloaders import myapi as myapi_downloader
from parsers.myapi import MyAPIParser

APIS = {
    # existing entries ...
    "myapi": {
        "downloader": myapi_downloader,
        "parser":     MyAPIParser(),
        "index_key":  "xml_dir",   # key in downloader's return dict pointing to parser input
    },
}
```

---

## Index schema reference

Each symbol dict must contain these fields:

| Field         | Type        | Description                                      |
|---------------|-------------|--------------------------------------------------|
| `symbol`      | str         | Symbol name, e.g. `xTaskCreate`                  |
| `api`         | str         | API name, e.g. `freertos`                        |
| `version`     | str         | Version string, e.g. `V11.2.0`                   |
| `kind`        | str         | `function`, `macro`, `typedef`, `enum`, `struct` |
| `signature`   | str         | Full signature string                            |
| `params`      | list[dict]  | Each with `name`, `type`, `description`          |
| `returns`     | str         | Return type string, empty for void/macros        |
| `header`      | str         | Header filename, e.g. `task.h`                   |
| `description` | str         | Brief description                                |

---

## Format-specific parser modules

| Module               | Format       | Used by                  |
|----------------------|--------------|--------------------------|
| `parsers/doxygen.py` | Doxygen XML  | FreeRTOS, ESP-IDF (planned) |

Add new format modules here as they are introduced.
