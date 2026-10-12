#!/usr/bin/env python3
"""Daily range research collection with shared public-data capture and offline cache."""
import argparse
import os
import random
import time
import sys
from datetime import date
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python_scritps'))
from research_core.fetching import add_source_arguments, source_from_args
from research_core.io import atomic_csv, validate_symbol
from research_core.errors import ResearchError, safe_error_code
from research_core.runtime import RunLog

ETFS = 'SOXL SOXX SMH SPY QQQ IWM DIA XLK XLF XLE XLV XLI XLY XLP XLU XLB XLC XLRE XBI IBB TLT GLD SLV TQQQ SQQQ ARKK KRE HYG'.split()

def get(url, params):
    import requests
    r = requests.get('https://api.tradier.com/v1' + url, params=params, headers={'Authorization': 'Bearer ' + os.environ['TRADIER_TOKEN'], 'Accept': 'application/json'}, timeout=25)
    r.raise_for_status()
    return r.json()

def liquidity(s):
    try:
        q = get('/markets/quotes', {'symbols': s})['quotes']['quote']
        spot = float(q.get('last') or 0)
        dates = get('/markets/options/expirations', {'symbol': s})['expirations']['date']
        dates = [dates] if isinstance(dates, str) else dates
        today = pd.Timestamp.now().normalize()
        choices = []
        for lo, hi, target in [(4, 14, 7), (25, 50, 35)]:
            ds = [d for d in dates if lo <= (pd.Timestamp(d) - today).days <= hi]
            if ds:
                choices.append(min(ds, key=lambda d: abs((pd.Timestamp(d) - today).days - target)))
        spreads = []
        vol = []
        oi = []
        for date in choices:
            opts = get('/markets/options/chains', {'symbol': s, 'expiration': date})['options']['option']
            if isinstance(opts, dict):
                opts = [opts]
            for side in ('call', 'put'):
                subset = sorted((x for x in opts if x.get('option_type') == side), key=lambda x: abs(float(x['strike']) - spot))[:3]
                for x in subset:
                    b = float(x.get('bid') or 0)
                    a = float(x.get('ask') or 0)
                    if b > 0 and a >= b and ((a + b) / 2 >= 0.1):
                        spreads.append((a - b) / ((a + b) / 2))
                        vol.append(int(x.get('volume') or 0))
                        oi.append(int(x.get('open_interest') or 0))
        if len(spreads) < 6:
            return None
        return dict(symbol=s, spread=float(np.median(spreads)), volume=sum(vol), open_interest=sum(oi), contracts=len(spreads))
    except Exception as e:
        print('liquidity unavailable', safe_error_code(e))
        return None

def select(out, seed):
    import yfinance as yf
    if not os.getenv('TRADIER_TOKEN'):
        raise SystemExit('Set TRADIER_TOKEN (live quote entitlement) or provide --stocks-file')
    cache = out / 'top200.csv'
    if cache.exists():
        top = pd.read_csv(cache)
    else:
        t = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]
        rows = []
        for i, r in t.iterrows():
            s = r['Symbol'].replace('.', '-')
            try:
                cap = yf.Ticker(s).fast_info.get('market_cap')
            except Exception:
                cap = None
            if cap:
                rows.append((s, int(cap), r['GICS Sector']))
            if i % 50 == 0:
                print('market cap scan', i, flush=True)
        top = pd.DataFrame(rows, columns=['symbol', 'market_cap', 'sector']).nlargest(200, 'market_cap')
        top.to_csv(cache, index=False)
    snap = out / 'liquidity.csv'
    data = pd.read_csv(snap).to_dict('records') if snap.exists() else []
    done = {x['symbol'] for x in data}
    for s in top.symbol:
        if s in done:
            continue
        x = liquidity(s)
        if x:
            data.append(x)
            pd.DataFrame(data).to_csv(snap, index=False)
        time.sleep(0.15)
    if not data:
        raise ValueError('No eligible liquidity observations')
    d = pd.DataFrame(data)
    d = d[(d.spread <= 0.2) & (d.volume >= 100) & (d.open_interest >= 500)].copy()
    d['score'] = np.log1p(d.volume) + 0.3 * np.log1p(d.open_interest) - 12 * d.spread
    d = d.sort_values('score', ascending=False)
    d.to_csv(out / 'eligible_ranked.csv', index=False)
    pool = d.head(80).symbol.tolist()
    if len(pool) < 20:
        raise SystemExit('Fewer than 20 eligible stocks; no fallback to unverified liquidity.')
    selected = random.Random(seed).sample(pool, 20)
    pd.DataFrame({'symbol': selected, 'seed': seed}).to_csv(out / 'selected_20.csv', index=False)
    return (selected, dict(zip(top.symbol, top.sector)))

def ratio(a, b):
    return a / b.replace(0, np.nan)

def build(s, sector, start, end, maxx, source):
    """Fetch through the shared cache/capture boundary, then calculate offline."""
    data = source.history(s, start=start, end=end, auto_adjust=True, method='download')
    return calculate_features(data, s, sector, maxx)


def calculate_features(data, symbol, sector, max_horizon):
    """Preserve the existing daily feature definitions and future-session labels."""
    if max_horizon < 1:
        raise ValueError('max_x must be positive')
    prices = data.copy()
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise ValueError('History requires a DatetimeIndex')
    if prices.index.has_duplicates or not prices.index.is_monotonic_increasing:
        raise ValueError('History requires unique ordered timestamps')
    if isinstance(prices.columns, pd.MultiIndex):
        prices.columns = prices.columns.get_level_values(0)
    prices = prices[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
    prices = prices[prices.Volume > 0]
    if len(prices) < 250:
        raise ValueError('Not enough bars')
    open_price, high, low, close, volume = (
        prices[column].astype(float)
        for column in ['Open', 'High', 'Low', 'Close', 'Volume']
    )
    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    atr21 = true_range.ewm(alpha=1 / 21, adjust=False).mean()
    anchors = pd.DataFrame(index=prices.index)
    anchors['symbol'] = symbol
    anchors['sector'] = sector
    anchors['anchor_dt'] = prices.index.strftime('%Y-%m-%d')
    anchors['anchor_close'] = close
    anchors['atr21'] = atr21
    anchors['atr5_atr21'] = ratio(true_range.ewm(alpha=1 / 5, adjust=False).mean(), atr21)
    anchors['atr21_atr63'] = ratio(atr21, true_range.ewm(alpha=1 / 63, adjust=False).mean())
    log_returns = np.log(close / previous_close)
    for window in (5, 21, 63):
        anchors[f'rv{window}'] = log_returns.rolling(window).std() * np.sqrt(252)
    anchors['rv5_rv21'] = ratio(anchors.rv5, anchors.rv21)
    anchors['rv21_rv63'] = ratio(anchors.rv21, anchors.rv63)
    for window in (5, 10, 20, 40, 60):
        change = close - close.shift(window)
        path = close.diff().abs().rolling(window).sum()
        anchors[f'slope_{window}'] = ratio(change, window * atr21)
        anchors[f'eff_{window}'] = ratio(change.abs(), path)
        anchors[f'signed_eff_{window}'] = ratio(change, path)
    for window in (10, 20, 60, 126):
        rolling_high = high.rolling(window).max()
        rolling_low = low.rolling(window).min()
        anchors[f'range_pos_{window}'] = ratio(close - rolling_low, rolling_high - rolling_low)
        anchors[f'range_width_atr_{window}'] = ratio(rolling_high - rolling_low, atr21)
    body = close - open_price
    candle_range = high - low
    anchors['body_atr'] = ratio(body, atr21)
    anchors['body_fraction'] = ratio(body.abs(), candle_range)
    anchors['upper_wick_fraction'] = ratio(high - pd.concat([open_price, close], axis=1).max(axis=1), candle_range)
    anchors['lower_wick_fraction'] = ratio(pd.concat([open_price, close], axis=1).min(axis=1) - low, candle_range)
    anchors['anchor_tr_atr'] = ratio(true_range, atr21)
    gap = open_price - previous_close
    anchors['gap_atr'] = ratio(gap, atr21)
    anchors['abs_gap_atr'] = ratio(gap.abs(), atr21)
    anchors['gap5_mean_abs_atr'] = ratio(gap.abs().rolling(5).mean(), atr21)
    anchors['gap20_max_abs_atr'] = ratio(gap.abs().rolling(20).max(), atr21)
    anchors['volume_rel20'] = ratio(volume, volume.rolling(20).mean())
    anchors['volume_med20_med63'] = ratio(volume.rolling(20).median(), volume.rolling(63).median())
    dollar_volume = volume * close
    anchors['dollar_volume_rel20'] = ratio(dollar_volume, dollar_volume.rolling(20).mean())
    for window in (60, 126):
        past = pd.concat([close.shift(j) for j in range(1, window + 1)], axis=1)
        anchors[f'price_zone_hit_rate_{window}'] = past.sub(close, axis=0).abs().le(atr21 * 0.5, axis=0).sum(axis=1) / window
    anchors = anchors.replace([np.inf, -np.inf], np.nan).dropna()
    outcome_frames = []
    indices = prices.index.get_indexer(anchors.index)
    closing_values = close.to_numpy()
    for horizon in range(1, max_horizon + 1):
        valid_indices = indices[indices + horizon < len(prices)]
        count = len(valid_indices)
        if not count:
            continue
        eligible_anchors = anchors.iloc[:count]
        anchor_close = eligible_anchors.anchor_close.to_numpy()
        anchor_atr = eligible_anchors.atr21.to_numpy()
        ending = closing_values[valid_indices + horizon]
        # Shift a trailing window to the next horizon sessions; exclude the anchor.
        future_high = high.rolling(horizon).max().shift(-horizon).to_numpy()[valid_indices]
        future_low = low.rolling(horizon).min().shift(-horizon).to_numpy()[valid_indices]
        terminal_return = (ending - anchor_close) / anchor_atr
        outcome_frames.append(pd.DataFrame({
            'symbol': symbol,
            'anchor_dt': eligible_anchors.anchor_dt,
            'x_days': horizon,
            'end_close': ending,
            'terminal_return_atr': terminal_return,
            'terminal_return_pct': (ending / anchor_close - 1) * 100,
            'up_terminal_atr': np.maximum(terminal_return, 0),
            'down_terminal_atr': np.maximum(-terminal_return, 0),
            'up_excursion_atr': np.maximum((future_high - anchor_close) / anchor_atr, 0),
            'down_excursion_atr': np.maximum((anchor_close - future_low) / anchor_atr, 0),
            'up_excursion_pct': np.maximum((future_high / anchor_close - 1) * 100, 0),
            'down_excursion_pct': np.maximum((1 - future_low / anchor_close) * 100, 0),
        }))
    if not outcome_frames:
        raise ValueError('No complete future outcomes')
    return (anchors.reset_index(drop=True), pd.concat(outcome_frames, ignore_index=True))

def run(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--out', default='range_output')
    p.add_argument('--start', default='2015-01-01')
    p.add_argument('--end')
    p.add_argument('--max-x', type=int, default=60)
    p.add_argument('--seed', type=int, default=20261010)
    p.add_argument('--stocks-file')
    p.add_argument('--skip-stocks', action='store_true')
    p.add_argument('--select-stocks', action='store_true', help='Explicit user-run legacy Tradier liquidity selection; requires --fetch')
    p.add_argument('--only')
    add_source_arguments(p)
    args = p.parse_args(argv)
    if args.refresh and not args.fetch:
        p.error('--refresh requires --fetch')
    if args.max_x < 1:
        p.error('--max-x must be positive')
    if args.select_stocks and not args.fetch:
        p.error('--select-stocks requires --fetch')
    if args.select_stocks and (args.skip_stocks or args.stocks_file or args.only is not None):
        p.error('--select-stocks cannot be combined with an explicit universe')
    args.start = date.fromisoformat(args.start).isoformat()
    if args.end is not None:
        args.end = date.fromisoformat(args.end).isoformat()
        if args.start >= args.end:
            raise ResearchError('INVALID_DATE_RANGE')
    out = Path(args.out)
    symbols = ETFS.copy()
    sectors = {s: 'ETF' for s in ETFS}
    if args.stocks_file and args.only is None:
        t = pd.read_csv(args.stocks_file)
        if 'symbol' not in t.columns or t.empty:
            p.error('--stocks-file needs a nonempty symbol column')
        symbols += t.symbol.tolist()
        if 'sector' in t:
            sectors.update(dict(zip(t.symbol, t.sector)))
    elif args.select_stocks:
        if not args.only:
            out.mkdir(parents=True, exist_ok=True)
            stocks, sector_map = select(out, args.seed)
            symbols += stocks
            sectors.update(sector_map)
    if args.only is not None:
        symbols = [validate_symbol(x.strip()) for x in args.only.split(',')]
    symbols = list(dict.fromkeys(validate_symbol(value) for value in symbols))
    source = source_from_args(args)
    out.mkdir(parents=True, exist_ok=True)
    with RunLog('daily-collection', total=len(symbols)) as log:
        manifest = []
        for s in symbols:
            try:
                a, b = build(s, sectors.get(s, 'Unknown'), args.start, args.end, args.max_x, source)
                atomic_csv(a, out / f'{s}_anchors.csv.gz', index=False, compression='gzip')
                atomic_csv(b, out / f'{s}_outcomes.csv.gz', index=False, compression='gzip')
                manifest.append({
                    'symbol': s, 'anchors': len(a), 'outcomes': len(b),
                    'start': a.anchor_dt.min(), 'end': a.anchor_dt.max(), 'status': 'ok',
                })
            except Exception as e:
                manifest.append(dict(symbol=s, status='error', error=safe_error_code(e)))
                log.error(e)
            atomic_csv(pd.DataFrame(manifest), out / 'manifest.csv', index=False)
            log.progress(success=manifest[-1]['status'] == 'ok')
    failed = sum(row['status'] != 'ok' for row in manifest)
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
