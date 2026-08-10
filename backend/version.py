"""
Centralized version management for UDB.

The application version is derived from the first ``## Version`` heading in
``CHANGELOG.md`` (the same source the CLI uses via ``VersionManager``). This
keeps the CLI, GUI, packaging and GitHub Releases in lockstep.
"""

import os
import re
import sys


def _changelog_candidates() -> list:
    """Candidate locations for CHANGELOG.md, repo-first then bundle dirs."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(os.path.dirname(here), 'CHANGELOG.md'),   # repo: .../udb/CHANGELOG.md
    ]
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        candidates.append(os.path.join(base, 'CHANGELOG.md'))
        candidates.append(os.path.join(os.path.dirname(sys.executable), 'CHANGELOG.md'))
    return candidates


def get_version() -> str:
    """
    Return the current UDB version as a string, e.g. ``2.16.1``.

    The version is read from the topmost ``## Version`` line in CHANGELOG.md
    (bundled with the packaged app).
    """
    for changelog in _changelog_candidates():
        try:
            with open(changelog, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith('## Version'):
                        return stripped.split()[2]
        except OSError:
            continue
    return '0.0.0'


__version__ = get_version()
