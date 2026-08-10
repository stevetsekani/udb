"""
UDB backend package.

Provides a local API and service layer over the existing UDB downloader core.
The CLI (udb.py) remains the source of truth for download logic; this package
adds an orchestration layer for the desktop GUI.
"""

__author__ = 'UDB GUI Contributors'

__all__ = ['__version__']
