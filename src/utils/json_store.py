"""Atomic JSON persistence helpers shared by the settings/history/vocabulary stores.

Two guarantees the naive ``open(path, "w")`` pattern doesn't give:

1. ``write_json_atomic`` writes to a temp file and ``os.replace``s it into
   place, so a crash or power cut mid-write can never leave a truncated file.
2. ``backup_corrupt_file`` renames a corrupt file to ``.bak`` so recovery to
   defaults never destroys the evidence (or the user's data).
"""

import json
import os
from pathlib import Path
from typing import Optional


def write_json_atomic(path: Path, data: dict, indent: int = 2, ensure_ascii: bool = True) -> None:
    """Write JSON via temp file + os.replace so a crash can't truncate the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def backup_corrupt_file(path: Path) -> Optional[Path]:
    """Rename a corrupt file to ``<name>.bak`` instead of overwriting it.

    Returns the backup path, or None if the rename failed.
    """
    try:
        bak = path.with_suffix(path.suffix + ".bak")
        if bak.exists():
            bak.unlink()
        path.rename(bak)
        return bak
    except Exception:
        return None
