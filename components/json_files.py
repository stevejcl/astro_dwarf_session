"""Program files (ToDo / Current / Done / Error JSON) written atomically
(user-reported Oct 2026: "invalid JSON" once when starting a program just
modified, not reproducible). Written in place, a file was first emptied
then filled: a read at that moment - the Programs page, the scheduler
loop's ToDo poll, a run updating its status - found it empty or half
written. Written to a temporary file next to it then swapped in with
os.replace(), a reader always sees the old or the new content whole."""
from __future__ import annotations

import json
import os
import tempfile


def write_json_atomic(path: str, data, indent: int = 4) -> None:
    folder = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp-", suffix=".part", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def read_json(path: str) -> tuple[dict | None, str]:
    """(data, "") or (None, reason): "missing" when the file is no longer
    there (started and moved to Current, deleted...), else the JSON /
    read error's own text."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), ""
    except FileNotFoundError:
        return None, "missing"
    except (OSError, ValueError) as e:
        return None, str(e)
