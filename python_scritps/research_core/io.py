"""Portable, atomic outputs and validated symbol inputs."""
import csv
import os
from pathlib import Path
import re
import tempfile
from .errors import ResearchError


def validate_symbol(value):
    symbol = str(value).strip().upper()
    if not re.fullmatch(r'[A-Z0-9^][A-Z0-9.^=\-]{0,31}', symbol):
        raise ResearchError('INVALID_SYMBOL')
    return symbol


def symbols_from_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        rows = csv.DictReader(handle)
        if 'symbol' not in (rows.fieldnames or []):
            raise ResearchError('SYMBOL_COLUMN_REQUIRED')
        symbols = sorted({validate_symbol(row['symbol']) for row in rows if row.get('symbol', '').strip()})
    if not symbols:
        raise ResearchError('EMPTY_UNIVERSE')
    return symbols


def atomic_csv(frame, path, **kwargs):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, suffix=path.suffix, dir=path.parent)
    os.close(fd)
    try:
        frame.to_csv(temporary, encoding='utf-8', **kwargs)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


from contextlib import contextmanager


@contextmanager
def atomic_path(path):
    """Publish a completed artifact only when all writes succeed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, suffix=path.suffix, dir=path.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        yield temporary
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
