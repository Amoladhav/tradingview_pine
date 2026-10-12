"""Immutable decoded-table captures; JSON only, never executable pickle.

These artifacts preserve the yfinance DataFrame boundary, not Yahoo wire bytes.
Unknown scalar types fail explicitly rather than being silently stringified.
"""
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import uuid
import numpy as np
import pandas as pd
from .errors import ResearchError
from .io import atomic_path

MAX_CAPTURE_BYTES = 128 * 1024 * 1024


def encode(value):
    if value is pd.NA:
        return {'t': 'na'}
    if value is pd.NaT:
        return {'t': 'nat'}
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return {'t': 'datetime', 'v': value.isoformat()}
    if isinstance(value, np.generic):
        return encode(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return {'t': 'float', 'v': str(value)}
    if isinstance(value, tuple):
        return {'t': 'tuple', 'v': [encode(x) for x in value]}
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise ResearchError('CAPTURE_UNSUPPORTED_TYPE')


def decode(value):
    if not isinstance(value, dict):
        return value
    tag = value.get('t')
    if tag == 'na':
        return pd.NA
    if tag == 'nat':
        return pd.NaT
    if tag == 'datetime':
        return pd.Timestamp(value['v'])
    if tag == 'float':
        return float(value['v'])
    if tag == 'tuple':
        return tuple(decode(x) for x in value['v'])
    raise ResearchError('CAPTURE_INVALID')


def request_key(request):
    return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def profile_frame(frame):
    """Private descriptive profiles; no fields are discarded or interpreted."""
    profiles = []
    for position, column in enumerate(frame.columns):
        values = frame.iloc[:, position]
        nulls = values.isna()
        profiles.append({
            'column': encode(column), 'rows': len(values),
            'null_count': int(nulls.sum()),
            'blank_count': sum(isinstance(value, str) and not value.strip() for value in values),
            'observed_types': sorted({type(value).__name__ for value in values}),
            'dtype': str(values.dtype),
        })
    return profiles


def pack_frame(frame):
    return {
        'columns': [encode(x) for x in frame.columns],
        'column_names': [encode(x) for x in frame.columns.names],
        'multi_columns': isinstance(frame.columns, pd.MultiIndex),
        'index': [encode(x) for x in frame.index],
        'index_names': [encode(x) for x in frame.index.names],
        'datetime_index': isinstance(frame.index, pd.DatetimeIndex),
        'index_timezone': str(frame.index.tz) if isinstance(frame.index, pd.DatetimeIndex) and frame.index.tz is not None else None,
        'dtypes': [str(x) for x in frame.dtypes],
        'data': [[encode(x) for x in row] for row in frame.itertuples(index=False, name=None)],
    }


def unpack_frame(data):
    columns = [decode(x) for x in data['columns']]
    names = [decode(x) for x in data['column_names']]
    if data['multi_columns']:
        columns = pd.MultiIndex.from_tuples(columns, names=names)
    else:
        columns = pd.Index(columns, name=names[0])
    index = [decode(x) for x in data['index']]
    if data['datetime_index']:
        if data.get('index_timezone'):
            index = pd.to_datetime(index, utc=True).tz_convert(data['index_timezone'])
        else:
            index = pd.DatetimeIndex(index)
        index.name = decode(data['index_names'][0])
    else:
        index = pd.Index(index, name=decode(data['index_names'][0]))
    frame = pd.DataFrame([[decode(x) for x in row] for row in data['data']], index=index, columns=columns)
    for i, dtype in enumerate(data['dtypes']):
        frame.isetitem(i, frame.iloc[:, i].astype(dtype))
    return frame


class CaptureStore:
    def __init__(self, root):
        self.root = Path(root)

    def save(self, request, frame, version='unknown'):
        now = datetime.now(timezone.utc)
        directory = self.root / request_key(request)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = {'schema_version': 1, 'source': 'yfinance', 'boundary': 'decoded_dataframe',
                   'retrieved_at': now.isoformat(), 'library_version': version,
                   'request': request, 'acquisition_status': 'returned',
                   'completeness': 'provider_returned_not_verified',
                   'profile': profile_frame(frame), 'frame': pack_frame(frame)}
        body = json.dumps(payload, allow_nan=False, separators=(',', ':')).encode('utf-8')
        if len(body) > MAX_CAPTURE_BYTES:
            raise ResearchError('CAPTURE_TOO_LARGE')
        path = directory / (now.strftime('%Y%m%dT%H%M%S%f') + '-' + uuid.uuid4().hex + '.json')
        with atomic_path(path) as temporary:
            temporary.chmod(0o600)
            temporary.write_bytes(body)
        return path

    def load(self, request):
        paths = sorted((self.root / request_key(request)).glob('*.json'))
        if not paths:
            raise ResearchError('CACHE_MISS_USE_EXPLICIT_FETCH')
        path = paths[-1]
        try:
            if path.stat().st_size > MAX_CAPTURE_BYTES:
                raise ResearchError('CAPTURE_TOO_LARGE')
            payload = json.loads(path.read_text(encoding='utf-8'))
            if payload['schema_version'] != 1 or payload['request'] != request:
                raise ResearchError('CAPTURE_INVALID')
            return unpack_frame(payload['frame'])
        except ResearchError:
            raise
        except (ValueError, TypeError, KeyError, OSError):
            raise ResearchError('CAPTURE_INVALID') from None
