r"""
Persistent download history.

Uses SQLite (stdlib) stored in the platform app-data directory — no external
database server required. Records metadata for every download attempt so the
GUI can render a searchable, filterable history page.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime

from backend.app_config import get_history_db_path

_SCHEMA = '''
CREATE TABLE IF NOT EXISTS history (
    id TEXT PRIMARY KEY,
    title TEXT,
    episode TEXT,
    season INTEGER,
    quality TEXT,
    source TEXT,
    status TEXT,
    destination TEXT,
    file_size TEXT,
    date TEXT,
    error TEXT,
    client TEXT,
    extra TEXT
);
CREATE INDEX IF NOT EXISTS idx_history_date ON history(date);
CREATE INDEX IF NOT EXISTS idx_history_status ON history(status);
'''


class HistoryService:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or get_history_db_path()
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._lock = threading.Lock()
        # Keep a single connection so in-memory DBs (tests) work and file DBs
        # avoid connection churn. check_same_thread=False is safe because all
        # access is serialized through self._lock.
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def _connect(self):
        return self._conn

    def add(self, record: dict) -> None:
        """Insert or replace a history record."""
        row = {
            'id': record.get('id', ''),
            'title': record.get('title', ''),
            'episode': str(record.get('episode', '') or ''),
            'season': record.get('season'),
            'quality': record.get('quality', ''),
            'source': record.get('source', ''),
            'status': record.get('status', ''),
            'destination': record.get('destination', ''),
            'file_size': record.get('file_size', ''),
            'date': record.get('date', datetime.now().isoformat(timespec='seconds')),
            'error': record.get('error', ''),
            'client': record.get('client', ''),
            'extra': json.dumps(record.get('extra') or {}, ensure_ascii=False),
        }
        conn = self._connect()
        with self._lock:
            conn.execute(
                '''INSERT OR REPLACE INTO history
                   (id, title, episode, season, quality, source, status,
                    destination, file_size, date, error, client, extra)
                   VALUES
                   (:id, :title, :episode, :season, :quality, :source, :status,
                    :destination, :file_size, :date, :error, :client, :extra)''',
                row,
            )
            conn.commit()

    def update(self, record_id: str, fields: dict) -> None:
        if not fields:
            return
        allowed = ['title', 'episode', 'season', 'quality', 'source', 'status',
                   'destination', 'file_size', 'date', 'error', 'client', 'extra']
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        if 'extra' in updates:
            updates['extra'] = json.dumps(updates['extra'], ensure_ascii=False)
        assignments = ', '.join(f'{k} = ?' for k in updates)
        values = list(updates.values()) + [record_id]
        conn = self._connect()
        with self._lock:
            conn.execute(f'UPDATE history SET {assignments} WHERE id = ?', values)
            conn.commit()

    def list(self, status: str = None, search: str = None, limit: int = 200,
             sort_by: str = 'date', order: str = 'desc') -> list:
        """Return history records matching the filters, newest first."""
        query = 'SELECT * FROM history'
        conditions = []
        params = []
        if status:
            conditions.append('status = ?')
            params.append(status)
        if search:
            conditions.append('(title LIKE ? OR episode LIKE ? OR source LIKE ?)')
            like = f'%{search}%'
            params.extend([like, like, like])
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        sort_col = sort_by if sort_by in ('date', 'title', 'status', 'quality') else 'date'
        direction = 'ASC' if order == 'asc' else 'DESC'
        query += f' ORDER BY {sort_col} {direction}'
        if limit and limit > 0:
            query += ' LIMIT ?'
            params.append(limit)
        conn = self._connect()
        with self._lock:
            rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item['extra'] = json.loads(item.get('extra') or '{}')
            except (ValueError, TypeError):
                item['extra'] = {}
            result.append(item)
        return result

    def get(self, record_id: str):
        conn = self._connect()
        with self._lock:
            row = conn.execute('SELECT * FROM history WHERE id = ?', (record_id,)).fetchone()
        if row is None:
            return None
        item = dict(row)
        try:
            item['extra'] = json.loads(item.get('extra') or '{}')
        except (ValueError, TypeError):
            item['extra'] = {}
        return item

    def delete(self, record_id: str) -> bool:
        conn = self._connect()
        with self._lock:
            cur = conn.execute('DELETE FROM history WHERE id = ?', (record_id,))
            conn.commit()
            return cur.rowcount > 0

    def clear(self) -> None:
        conn = self._connect()
        with self._lock:
            conn.execute('DELETE FROM history')
            conn.commit()

    def counts(self) -> dict:
        """Return counts grouped by status."""
        conn = self._connect()
        with self._lock:
            rows = conn.execute('SELECT status, COUNT(*) AS c FROM history GROUP BY status').fetchall()
        counts = {'completed': 0, 'failed': 0, 'cancelled': 0, 'other': 0}
        for row in rows:
            status = row['status']
            if status in counts:
                counts[status] += row['c']
            else:
                counts['other'] += row['c']
        return counts

    def total_downloaded(self) -> float:
        """
        Return an approximate total downloaded size in bytes, parsed from the
        ``file_size`` strings (e.g. '734.0 MB') stored for completed records.
        """
        sizes = self.list(status='completed', limit=10000)
        total = 0.0
        for item in sizes:
            size_str = item.get('file_size') or ''
            total += _parse_size_mb(size_str) * (1024 * 1024)
        return total


def _parse_size_mb(size_str: str) -> float:
    """Parse a size string like '734.0 MB', '1.2 GB' into MB (float)."""
    try:
        parts = size_str.strip().split()
        if len(parts) != 2:
            return 0.0
        value = float(parts[0])
        unit = parts[1].upper()
        if unit == 'GB':
            return value * 1024
        if unit in ('MB', 'MIB'):
            return value
        if unit == 'KB':
            return value / 1024
        if unit == 'B':
            return value / (1024 * 1024)
        return value
    except (ValueError, IndexError):
        return 0.0

