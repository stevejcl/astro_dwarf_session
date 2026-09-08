"""Per-device session directory resolution (ToDo/Current/Done/Error/
Results), mirroring astro_dwarf_scheduler.py's own convention EXACTLY
(see setup_new_config()/get_current_config_py_file() there) - so files
saved from this app land precisely where check_and_execute_commands()
actually looks for them, and nowhere else.

The convention: a session's config_py_path is "config_<name>.py" (or
bare "config.py" for the special "Default" profile) - astro_dwarf_
scheduler.py derives its per-device Devices_Sessions/<name>/Astro_
Sessions folder from that same <name>. Our own pairing.py already
creates config_<slug>.py/.ini files using this exact naming (see
_slugify()), so <name> here is the same slug."""
from __future__ import annotations

import os

_DEFAULT_CONFIG_NAME = "Default"


def config_name_for_session(session) -> str:
    """Derives astro_dwarf_scheduler.py's "config_name" from a session's
    own config_py_path - "config_d3.py" -> "d3", bare "config.py" ->
    "Default" (matching CONFIG_DEFAULT there)."""
    basename = os.path.splitext(os.path.basename(session.config.config_py_path))[0]
    if basename == "config":
        return _DEFAULT_CONFIG_NAME
    if basename.startswith("config_"):
        return basename[len("config_"):]
    return basename


def session_dirs_for(session) -> dict[str, str]:
    """Returns the same five paths as astro_dwarf_scheduler.py's own
    LIST_ASTRO_DIR, for THIS session's device specifically."""
    base_dir = os.path.abspath(".")
    config_name = config_name_for_session(session)

    if config_name == _DEFAULT_CONFIG_NAME:
        sessions_dir = os.path.join(base_dir, "Astro_Sessions")
    else:
        sessions_dir = os.path.join(base_dir, "Devices_Sessions", config_name, "Astro_Sessions")

    return {
        "SESSIONS_DIR": sessions_dir,
        "TODO_DIR": os.path.join(sessions_dir, "ToDo"),
        "CURRENT_DIR": os.path.join(sessions_dir, "Current"),
        "DONE_DIR": os.path.join(sessions_dir, "Done"),
        "ERROR_DIR": os.path.join(sessions_dir, "Error"),
        "RESULTS_DIR": os.path.join(sessions_dir, "Results"),
    }


def ensure_dirs(session) -> dict[str, str]:
    """Like session_dirs_for(), but also creates any missing directory -
    convenient right before writing a new program file, since a
    freshly-paired device won't have these folders yet."""
    dirs = session_dirs_for(session)
    for path in dirs.values():
        os.makedirs(path, exist_ok=True)
    return dirs
