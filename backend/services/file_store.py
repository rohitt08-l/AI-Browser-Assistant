"""Short-lived storage for generated files (PDFs).

Files live in a dedicated directory (a temp dir by default, never the repo)
under random IDs and are deleted after `ttl_seconds`. IDs are validated
against a strict pattern so they can never be used for path traversal.
"""

from __future__ import annotations

import re
import tempfile
import time
import uuid
from pathlib import Path

_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class FileStore:
    def __init__(self, directory: str | None, ttl_seconds: int):
        self._dir = Path(directory) if directory else Path(tempfile.gettempdir()) / "ai-browser-assistant"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ttl = ttl_seconds

    def save(self, data: bytes, suffix: str = ".pdf") -> str:
        self.cleanup()
        file_id = uuid.uuid4().hex
        (self._dir / f"{file_id}{suffix}").write_bytes(data)
        return file_id

    def path(self, file_id: str, suffix: str = ".pdf") -> Path | None:
        if not _ID_RE.fullmatch(file_id):
            return None
        path = self._dir / f"{file_id}{suffix}"
        if not path.is_file() or self._expired(path):
            return None
        return path

    def cleanup(self) -> None:
        for path in self._dir.glob("*"):
            if path.is_file() and self._expired(path):
                path.unlink(missing_ok=True)

    def _expired(self, path: Path) -> bool:
        return time.time() - path.stat().st_mtime > self._ttl
