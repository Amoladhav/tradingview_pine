"""Explicit public fetching with immutable decoded capture and offline replay."""
import contextlib
import io
import logging
from pathlib import Path
import time
from .capture import CaptureStore
from .errors import ResearchError
from .io import validate_symbol


class YahooSource:
    def __init__(self, cache_dir=Path('artifacts/private/research-cache'), mode='cache', pause=0.15, refresh=False):
        if mode not in ('cache', 'fetch') or pause < 0:
            raise ResearchError('INVALID_SOURCE_SETTINGS')
        self.store = CaptureStore(cache_dir)
        self.mode = mode
        self.pause = pause
        self.refresh = refresh

    def _cached(self, request):
        frame = self.store.load(request)
        if frame.empty:
            raise ResearchError('PUBLIC_FETCH_EMPTY')
        return frame

    def _get(self, request, fetch):
        if self.mode == 'cache':
            return self._cached(request)
        if not self.refresh:
            try:
                return self._cached(request)
            except ResearchError as exc:
                if exc.code != 'CACHE_MISS_USE_EXPLICIT_FETCH':
                    raise
        # Lazy import: offline commands do not initialize provider clients.
        try:
            import yfinance as yf
        except ImportError:
            raise ResearchError('YFINANCE_NOT_INSTALLED') from None
        logger = logging.getLogger('yfinance')
        previous_disabled = logger.disabled
        try:
            # Provider diagnostics can contain URLs and source identifiers.
            logger.disabled = True
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                frame = fetch(yf)
        except Exception:
            raise ResearchError('PUBLIC_FETCH_FAILED') from None
        finally:
            logger.disabled = previous_disabled
            if self.pause:
                time.sleep(self.pause)
        if frame is None:
            raise ResearchError('PUBLIC_FETCH_EMPTY')
        self.store.save(request, frame, getattr(yf, '__version__', 'unknown'))
        if frame.empty:
            raise ResearchError('PUBLIC_FETCH_EMPTY')
        return frame

    def history(self, symbol, interval='1d', period=None, start=None, end=None,
                auto_adjust=True, actions=False, prepost=False, method='download'):
        symbol = validate_symbol(symbol)
        if method not in ('download', 'history'):
            raise ResearchError('INVALID_HISTORY_METHOD')
        settings = {'interval': interval, 'auto_adjust': auto_adjust, 'actions': actions, 'prepost': prepost, 'keepna': True}
        for key, value in (('period', period), ('start', start), ('end', end)):
            if value is not None:
                settings[key] = str(value)
        request = {'kind': 'history', 'method': method, 'symbol': symbol, **settings}
        def fetch(yf):
            if method == 'history':
                return yf.Ticker(symbol).history(**settings)
            return yf.download(symbol, progress=False, threads=False, **settings)
        return self._get(request, fetch)

    def earnings(self, symbol, limit=100):
        symbol = validate_symbol(symbol)
        if limit < 1:
            raise ResearchError('INVALID_EARNINGS_LIMIT')
        return self._get({'kind': 'earnings', 'symbol': symbol, 'limit': limit},
                         lambda yf: yf.Ticker(symbol).get_earnings_dates(limit=limit))


def add_source_arguments(parser):
    parser.add_argument('--fetch', action='store_true', help='Explicitly fetch public Yahoo data; default replays cached captures only.')
    parser.add_argument('--refresh', action='store_true', help='Fetch a new immutable capture even when cached; requires --fetch.')
    parser.add_argument('--cache-dir', type=Path, default=Path('artifacts/private/research-cache'))
    return parser


def source_from_args(args):
    if getattr(args, 'refresh', False) and not args.fetch:
        raise ResearchError('REFRESH_REQUIRES_FETCH')
    return YahooSource(cache_dir=args.cache_dir, mode='fetch' if args.fetch else 'cache', refresh=getattr(args, 'refresh', False))


def fetch_json(session, url, params, capture_dir, *, source='tradier_sandbox', max_bytes=8 * 1024 * 1024):
    """One bounded request; capture successful bodies before JSON interpretation.

    The caller owns explicit authentication. Headers and URL are never persisted.
    Error responses are not captured because they may contain sensitive material.
    """
    from datetime import datetime, timezone
    import json
    import uuid
    root = Path(capture_dir)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        with session.get(url, params=params, timeout=25, stream=True) as response:
            response.raise_for_status()
            chunks = []
            size = 0
            for chunk in response.iter_content(chunk_size=65536):
                size += len(chunk)
                if size > max_bytes:
                    raise ResearchError('RESPONSE_TOO_LARGE')
                chunks.append(chunk)
            body = b''.join(chunks)
    except ResearchError:
        raise
    except Exception:
        raise ResearchError('PROVIDER_REQUEST_FAILED') from None
    capture_id = uuid.uuid4().hex
    path = root / (capture_id + '.body')
    with path.open('xb') as handle:
        handle.write(body)
    path.chmod(0o600)
    metadata = {'schema_version': 1, 'source': source,
                'retrieved_at': datetime.now(timezone.utc).isoformat(),
                'boundary': 'decoded_http_body_bytes', 'acquisition_status': 'returned',
                'completeness': 'provider_returned_not_verified'}
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict) or payload.get('errors'):
            metadata['acquisition_status'] = 'invalid_payload'
            raise ResearchError('PROVIDER_INVALID_PAYLOAD')
    except (ValueError, UnicodeDecodeError):
        metadata['acquisition_status'] = 'invalid_json'
        raise ResearchError('PROVIDER_INVALID_JSON') from None
    finally:
        meta_path = root / (capture_id + '.json')
        with meta_path.open('x', encoding='utf-8') as handle:
            json.dump(metadata, handle)
        meta_path.chmod(0o600)
    return payload
