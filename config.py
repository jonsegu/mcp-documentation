from __future__ import annotations

import os
from pathlib import Path


def _default_documentation_root() -> Path:
    return Path("/mnt/c/documentacion")


DOCUMENTATION_ROOT = Path(os.getenv("DOCUMENTATION_ROOT", _default_documentation_root())).expanduser()
ALLOWED_EXTENSIONS = {".md", ".txt"}
MAX_DOCUMENT_BYTES = int(os.getenv("MAX_DOCUMENT_BYTES", str(2 * 1024 * 1024)))
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "20"))
MAX_MATCHES_PER_DOCUMENT = int(os.getenv("MAX_MATCHES_PER_DOCUMENT", "5"))
SEARCH_CONTEXT_LINES = int(os.getenv("SEARCH_CONTEXT_LINES", "1"))
