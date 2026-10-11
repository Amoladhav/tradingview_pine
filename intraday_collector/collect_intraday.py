#!/usr/bin/env python3
"""Collect and audit US regular-session intraday OHLCV for range research.
Yahoo/yfinance limits: 30m ~60 calendar days; 60m ~730 calendar days.
No future labels or predictions are generated here.
"""
import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

ET = ZoneInfo('America/New_York')
DEFAULT = 'SOXL SOXX SMH SPY QQQ IWM TQQQ SQQQ NVDA AMD AAPL MSFT META AMZN GOOGL TSLA GLD TLT XLE XLF'.split()

def collect(symbol, interval, period, retries):
    for attempt in range(retries + 1):
        try:
            data = yf.Ticker(symbol).history(period=period, interval=interval,
                prepost=False, auto_adjust=False, actions=False, raise_errors=True, timeout=25)
            if data.empty:
                raise RuntimeError('Provider returned no bars')
            return data
        except Exception as exc:
            if attempt == retries:
                raise RuntimeError(f'{symbol} {interval}: {exc}') from exc
            delay = min(4 * (2 ** attempt), 30)
            logging.warning('%s %s attempt %s failed: %s; retry in %ss', symbol, interval, attempt + 1, exc, delay)
            time.sleep(delay)

def normalize(data, symbol, interval):
    if data.index.tz is None:
        raise ValueError('Provider returned timezone-naive timestamps; refusing ambiguous data')
    frame = data.copy()
    frame.index = frame.index.tz_convert(ET)
    frame = frame.rename(columns={'Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'})
    frame = frame[['open','high','low','close','volume']].reset_index()
    frame = frame.rename(columns={frame.columns[0]:'timestamp'})
    frame['timestamp'] = pd.to_datetime(frame['timestamp'], utc=True).dt.tz_convert(ET)
    mins = frame['timestamp'].dt.hour * 60 + frame['timestamp'].dt.minute
    # Intraday timestamps represent bar START; 60m Yahoo bars may include a 15:30 bar.
    frame = frame[(frame.timestamp.dt.dayofweek < 5) & (mins >= 570) & (mins < 960)].copy()
    frame['session_date'] = frame.timestamp.dt.strftime('%Y-%m-%d')
    frame['timestamp_et'] = frame.timestamp.dt.strftime('%Y-%m-%dT%H:%M:%S%z')
    frame['timestamp_utc'] = frame.timestamp.dt.tz_convert('UTC').dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    frame['symbol'] = symbol
    frame['interval'] = interval
    frame = frame.drop(columns=['timestamp'])
    cols=['symbol','interval','timestamp_utc','timestamp_et','session_date','open','high','low','close','volume']
    return frame[cols].sort_values('timestamp_utc').drop_duplicates(['timestamp_utc'])

def audit(frame, interval):
    x = frame[['open','high','low','close','volume']].apply(pd.to_numeric, errors='coerce')
    invalid = (~np.isfinite(x.to_numpy())).any(axis=1) | (x[['open','high','low','close']] <= 0).any(axis=1) | (x.volume < 0)
    invalid |= (x.high < x[['open','close','low']].max(axis=1)) | (x.low > x[['open','close','high']].min(axis=1))
    frame = frame.loc[~invalid].copy()
    n_by_day = frame.groupby('session_date').size()
    # 30m regular sessions generally 13 bars; early closes have fewer.
    # 60m bars vary by provider: do not silently claim full 60-minute candles.
    return frame, {'invalid_rows_dropped':int(invalid.sum()),'session_days':int(len(n_by_day)),
        'bars_per_session_min':int(n_by_day.min()) if len(n_by_day) else 0,
        'bars_per_session_median':float(n_by_day.median()) if len(n_by_day) else 0,
        'bars_per_session_max':int(n_by_day.max()) if len(n_by_day) else 0,
        'sessions_with_fewer_than_expected_bars':int((n_by_day < (13 if interval=='30m' else 7)).sum())}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--only',nargs='+',help='Only specified tickers, e.g. --only SOXL SOXX SPY')
    p.add_argument('--interval',choices=['30m','60m'],default='30m')
    p.add_argument('--period',default=None,help='Default: 59d for 30m, 720d for 60m; provider may limit lookback')
    p.add_argument('--out',default='intraday_data')
    p.add_argument('--retries',type=int,default=2)
    p.add_argument('--pause',type=float,default=1.5)
    args=p.parse_args()
    period=args.period or ('59d' if args.interval=='30m' else '720d')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    symbols=list(dict.fromkeys(s.upper().strip() for s in (args.only or DEFAULT) if s.strip()))
    manifest=[]
    for sym in symbols:
        print(f'Fetching {sym}: {args.interval}, {period}',flush=True)
        try:
            raw=collect(sym,args.interval,period,args.retries)
            clean,stats=audit(normalize(raw,sym,args.interval),args.interval)
            if clean.empty: raise RuntimeError('No valid RTH bars after filtering')
            path=out/f'{sym}_{args.interval}_ohlcv.csv.gz'
            if path.exists():
                old=pd.read_csv(path)
                clean=pd.concat([old,clean],ignore_index=True).drop_duplicates('timestamp_utc',keep='last').sort_values('timestamp_utc')
            clean.to_csv(path,index=False,compression='gzip')
            record={'symbol':sym,'status':'ok','rows':len(clean),'first':clean.timestamp_et.iloc[0],
                'last':clean.timestamp_et.iloc[-1],**stats}
            print(f'  OK {len(clean)} bars ({record["first"]} to {record["last"]})',flush=True)
        except Exception as exc:
            record={'symbol':sym,'status':'failed','error':str(exc)}
            print(f'  FAILED: {exc}',flush=True)
        manifest.append(record)
        pd.DataFrame(manifest).to_csv(out/'manifest.csv',index=False)
        time.sleep(max(0,args.pause))
    metadata={'source':'Yahoo Finance via yfinance','collected_utc':datetime.now(timezone.utc).isoformat(),
        'interval':args.interval,'requested_period':period,'regular_session':'09:30–16:00 America/New_York',
        'auto_adjust':False,'note':'Raw provider OHLCV; not split-adjusted. Investigate corporate actions before modeling. Timestamp is bar start. 60m may include a final 30m bar. Data may be delayed/incomplete; audit manifest and exclude unfinished bars.'}
    (out/'collection_metadata.json').write_text(json.dumps(metadata,indent=2))
    if all(r['status']=='failed' for r in manifest): raise SystemExit('All downloads failed; see manifest.csv')

if __name__=='__main__':main()
