import os

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR  = os.path.join(BASE_DIR, "docs")
INDEX_DIR = os.path.join(BASE_DIR, "index")

# Fuzzy search settings (used by search.py)
FUZZY_THRESHOLD = 0.85  # minimum Jaro-Winkler similarity score (0.0–1.0)
FUZZY_TOP_N     = 3     # maximum number of fuzzy candidates to return