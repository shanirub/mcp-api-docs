import os

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR  = os.path.join(BASE_DIR, "docs")
INDEX_DIR = os.path.join(BASE_DIR, "index")

# Fuzzy search settings (used by search.py)
FUZZY_THRESHOLD = 0.85  # minimum Jaro-Winkler similarity score (0.0–1.0)
FUZZY_TOP_N     = 3     # maximum number of fuzzy candidates to return

# ESP-IDF components to ingest.
# Key:   component name — used as API name in the index (e.g. "esp_driver_i2c")
# Value: path relative to the sparse-checked-out source root where
#        Doxygen should look for public headers (INPUT in Doxyfile)
ESP_IDF_COMPONENTS = {
    "esp_driver_i2c":  "components/esp_driver_i2c/include/driver",
    "esp_driver_uart": "components/esp_driver_uart/include/driver",
    "esp_driver_gpio": "components/esp_driver_gpio/include/driver",
    "esp_wifi":        "components/esp_wifi/include",
    "esp_http_server": "components/esp_http_server/include",
    "esp_timer":       "components/esp_timer/include",
}
