"""Collect and audit US regular-session intraday OHLCV for range research.
Yahoo/yfinance limits: 30m ~60 calendar days; 60m ~730 calendar days.
No future labels or predictions are generated here.
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python_scritps'))
from research_core.fetching import add_source_arguments, source_from_args
from research_core.io import atomic_csv, validate_symbol
from research_core.errors import ResearchError, safe_error_code
from research_core.runtime import RunLog
ET = ZoneInfo('America/New_York')
DEFAULT = 'SOXL SOXX SMH SPY QQQ IWM TQQQ SQQQ NVDA AMD AAPL MSFT META AMZN GOOGL TSLA GLD TLT XLE XLF'.split()

def collect(symbol, interval, period, retries, source):
    """Use shared capture/cache; retries remain explicit and bounded by the caller."""
    for attempt in range(retries + 1):
        try:
            return source.history(
                symbol, period=period, interval=interval, prepost=False,
                auto_adjust=False, actions=False, method='history',
            )
        except Exception:
            if attempt == retries or source.mode == 'cache':
                raise
            time.sleep(min(4 * 2 ** attempt, 30))

def normalize(data, symbol, interval):
    if data.index.tz is None:
        raise ValueError('Provider returned timezone-naive timestamps; refusing ambiguous data')
    frame = data.copy()
    frame.index = frame.index.tz_convert(ET)
    frame = frame.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
    frame = frame[['open', 'high', 'low', 'close', 'volume']].reset_index()
    frame = frame.rename(columns={frame.columns[0]: 'timestamp'})
    frame['timestamp'] = pd.to_datetime(frame['timestamp'], utc=True).dt.tz_convert(ET)
    # Provider timestamps identify bar starts; the final 60m candle may be partial.
    mins = frame['timestamp'].dt.hour * 60 + frame['timestamp'].dt.minute
    frame = frame[(frame.timestamp.dt.dayofweek < 5) & (mins >= 570) & (mins < 960)].copy()
    frame['session_date'] = frame.timestamp.dt.strftime('%Y-%m-%d')
    frame['timestamp_et'] = frame.timestamp.dt.strftime('%Y-%m-%dT%H:%M:%S%z')
    frame['timestamp_utc'] = frame.timestamp.dt.tz_convert('UTC').dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    frame['symbol'] = symbol
    frame['interval'] = interval
    frame = frame.drop(columns=['timestamp'])
    cols = ['symbol', 'interval', 'timestamp_utc', 'timestamp_et', 'session_date', 'open', 'high', 'low', 'close', 'volume']
    return frame[cols].sort_values('timestamp_utc').drop_duplicates(['timestamp_utc'])

def audit(frame, interval):
    x = frame[['open', 'high', 'low', 'close', 'volume']].apply(pd.to_numeric, errors='coerce')
    invalid = (
        (~np.isfinite(x.to_numpy())).any(axis=1)
        | (x[['open', 'high', 'low', 'close']] <= 0).any(axis=1)
        | (x.volume < 0)
    )
    invalid |= (
        (x.high < x[['open', 'close', 'low']].max(axis=1))
        | (x.low > x[['open', 'close', 'high']].min(axis=1))
    )
    frame = frame.loc[~invalid].copy()
    n_by_day = frame.groupby('session_date').size()
    # Counts cover observed days only; holidays and entirely absent days need a calendar.
    return frame, {
        'invalid_rows_dropped': int(invalid.sum()),
        'session_days': int(len(n_by_day)),
        'bars_per_session_min': int(n_by_day.min()) if len(n_by_day) else 0,
        'bars_per_session_median': float(n_by_day.median()) if len(n_by_day) else 0,
        'bars_per_session_max': int(n_by_day.max()) if len(n_by_day) else 0,
        'sessions_with_fewer_than_expected_bars': int(
            (n_by_day < (13 if interval == '30m' else 7)).sum()
        ),
    }

def run(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--only', nargs='+', help='Only specified tickers, e.g. --only SOXL SOXX SPY')
    p.add_argument('--interval', choices=['30m', '60m'], default='30m')
    p.add_argument('--period', default=None, help='Default: 59d for 30m, 720d for 60m; provider may limit lookback')
    p.add_argument('--out', default='intraday_data')
    p.add_argument('--retries', type=int, default=2)
    p.add_argument('--pause', type=float, default=1.5)
    add_source_arguments(p)
    args = p.parse_args(argv)
    if args.refresh and not args.fetch:
        p.error('--refresh requires --fetch')
    if args.retries < 0 or args.retries > 10 or not np.isfinite(args.pause) or args.pause < 0:
        p.error('--retries must be 0..10 and --pause must be nonnegative')
    period = args.period or ('59d' if args.interval == '30m' else '720d')
    out = Path(args.out)
    symbols = list(dict.fromkeys((validate_symbol(s) for s in args.only or DEFAULT)))
    if not period.strip():
        raise ResearchError('INVALID_PERIOD')
    source = source_from_args(args)
    out.mkdir(parents=True, exist_ok=True)
    with RunLog('intraday-collection', total=len(symbols)) as log:
        manifest = []
        for sym in symbols:
            try:
                raw = collect(sym, args.interval, period, args.retries, source)
                clean, stats = audit(normalize(raw, sym, args.interval), args.interval)
                if clean.empty:
                    raise RuntimeError('No valid RTH bars after filtering')
                path = out / f'{sym}_{args.interval}_ohlcv.csv.gz'
                if path.exists():
                    old = pd.read_csv(path)
                    clean = (
                        pd.concat([old, clean], ignore_index=True)
                        .drop_duplicates('timestamp_utc', keep='last')
                        .sort_values('timestamp_utc')
                    )
                atomic_csv(clean, path, index=False, compression='gzip')
                record = {
                    'symbol': sym, 'status': 'ok', 'rows': len(clean),
                    'first': clean.timestamp_et.iloc[0],
                    'last': clean.timestamp_et.iloc[-1], **stats,
                }
            except Exception as exc:
                record = {'symbol': sym, 'status': 'failed', 'error': safe_error_code(exc)}
                log.error(exc)
            manifest.append(record)
            atomic_csv(pd.DataFrame(manifest), out / 'manifest.csv', index=False)
            log.progress(success=record['status'] == 'ok')
            if source.mode == 'fetch':
                time.sleep(args.pause)
        metadata = {
            'source': 'Yahoo Finance via yfinance',
            'collected_utc': datetime.now(timezone.utc).isoformat(),
            'interval': args.interval,
            'requested_period': period,
            'regular_session': '09:30–16:00 America/New_York',
            'auto_adjust': False,
            'note': (
                'Derived OHLCV from decoded yfinance tables; upstream split adjustments '
                'may already apply. Investigate corporate actions before modeling. '
                'Timestamp is bar start. 60m may include a final 30m bar. Data may be '
                'delayed/incomplete; audit manifest and exclude unfinished bars.'
            ),
        }
        (out / 'collection_metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    failed = sum((row['status'] == 'failed' for row in manifest))
    return 1 if failed else 0


def main(argv=None):
    """CLI boundary: keep cancellation and terminal failures concise and sanitized."""
    try:
        return run(argv)
    except KeyboardInterrupt:
        print('COLLECTION CANCELLED')
        return 130
    except Exception as exc:
        print(safe_error_code(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
