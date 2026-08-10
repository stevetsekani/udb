"""
Centralized version management for UDB.

The application version is derived from the first ``## Version`` heading in
``CHANGELOG.md`` (the same source the CLI uses via ``VersionManager``). This
keeps the CLI, GUI, packaging and GitHub Releases in lockstep.
"""

import os
import re


def get_version() -> str:
    """
    Return the current UDB version as a string, e.g. ``2.16.1``.

    The version is read from the topmost ``## Version`` line in CHANGELOG.md.
    """
    changelog = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'CHANGELOG.md')
    try:
        with open(changelog, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith('## Version'):
                    return stripped.split()[2]
    except OSError:
        pass
    return '0.0.0'


__version__ = get_version()
