#!/usr/bin/env python3
"""Tradier SANDBOX daily ATM option snapshot collector (research only).

Sandbox Greeks/IV are not supplied. This script calculates an APPROXIMATE
Black-Scholes IV from delayed option bid/ask midpoints, assuming European
exercise and a configurable continuously-compounded risk-free rate and dividend
yield. US equity options are generally American-style; dividend assumptions,
stale quotes, wide spreads and earnings can materially bias the approximation.

Outputs append/upsert to tradier_iv_snapshots.csv and tradier_iv_contracts.csv.
Never interprets these as historical backfilled observations.
"""
import argparse
import csv
import datetime as dt
import math
import os
import sys
import time
from pathlib import Path

import requests
from scipy.optimize import brentq
from scipy.stats import norm

BASE = 'https://sandbox.tradier.com/v1'
TARGETS = (7, 14, 30, 60)


def api(session, path, params):
    for attempt in range(4):
        try:
            r = session.get(BASE + path, params=params, timeout=25)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            payload = r.json()
            if isinstance(payload, dict) and payload.get('errors'):
                raise RuntimeError(str(payload['errors']))
            return payload
        except (requests.RequestException, ValueError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError('API request failed')


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def num(x):
    try:
        n = float(x)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def bs_price(s, k, t, r, q, sigma, option_type):
    if t <= 0 or sigma <= 0:
        return None
    z = sigma * math.sqrt(t)
    d1 = (math.log(s / k) + (r - q + sigma * sigma / 2) * t) / z
    d2 = d1 - z
    if option_type == 'call':
        return s * math.exp(-q * t) * norm.cdf(d1) - k * math.exp(-r * t) * norm.cdf(d2)
    return k * math.exp(-r * t) * norm.cdf(-d2) - s * math.exp(-q * t) * norm.cdf(-d1)


def implied_vol(s, k, t, mid, r, q, option_type):
    if any(x is None for x in (s, k, t, mid)) or min(s, k, t, mid) <= 0:
        return None
    lower = max(0.0, s * math.exp(-q * t) - k * math.exp(-r * t)) if option_type == 'call' else max(0.0, k * math.exp(-r * t) - s * math.exp(-q * t))
    if mid <= lower + 1e-8:
        return None
    try:
        lo, hi = 0.0001, 5.0
        if not (bs_price(s, k, t, r, q, lo, option_type) <= mid <= bs_price(s, k, t, r, q, hi, option_type)):
            return None
        return brentq(lambda v: bs_price(s, k, t, r, q, v, option_type) - mid, lo, hi)
    except (ValueError, OverflowError):
        return None


def write_upsert(path, rows, keys):
    if not rows:
        return
    previous = []
    if path.exists():
        with path.open(newline='') as f:
            previous = list(csv.DictReader(f))
    combined = {tuple(str(row.get(k, '')) for k in keys): row for row in previous + rows}
    fields = list(dict.fromkeys(k for row in previous + rows for k in row))
    tmp = path.with_suffix('.tmp')
    with tmp.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(combined.values())
    tmp.replace(path)


def symbols_from_csv(path):
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        if 'symbol' not in (reader.fieldnames or []):
            raise ValueError('Input CSV must contain symbol column')
        return sorted({row['symbol'].strip().upper() for row in reader if row.get('symbol', '').strip()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols', default='AAPL', help='Comma-separated tickers')
    parser.add_argument('--symbols-csv', help='CSV with symbol column, e.g. universe.csv')
    parser.add_argument('--rate', type=float, default=0.04, help='Assumed annual risk-free rate decimal, default 0.04')
    parser.add_argument('--dividend-yield', type=float, default=0.0, help='Assumed annual dividend yield decimal, default 0; inaccurate for dividend payers')
    parser.add_argument('--outdir', default='.', help='Output directory')
    parser.add_argument('--pause', type=float, default=0.2, help='Seconds between requests')
    args = parser.parse_args()

    token = os.environ.get('TRADIER_SANDBOX_TOKEN', '').strip()
    if not token:
        sys.exit('Set TRADIER_SANDBOX_TOKEN environment variable (do not paste key into code).')
    symbols = symbols_from_csv(args.symbols_csv) if args.symbols_csv else sorted({s.strip().upper() for s in args.symbols.split(',') if s.strip()})
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({'Authorization': f'Bearer {token}', 'Accept': 'application/json'})
    now = dt.datetime.now(dt.timezone.utc)
    snapshot_date = now.date().isoformat()
    summary_rows, contract_rows = [], []

    for symbol in symbols:
        try:
            quote_payload = api(session, '/markets/quotes', {'symbols': symbol})
            quote = quote_payload.get('quotes', {}).get('quote')
            quote = as_list(quote)
            quote = quote[0] if quote else {}
            spot = num(quote.get('last')) or num(quote.get('close'))
            if not spot or spot <= 0:
                raise ValueError('No usable underlying price')
            expiration_payload = api(session, '/markets/options/expirations', {'symbol': symbol, 'includeAllRoots': 'false'})
            expiration_dates = expiration_payload.get('expirations') or {}
            expirations = as_list(expiration_dates.get('date') if isinstance(expiration_dates, dict) else None)
            expiry_map = {}
            for exp in expirations:
                exp_date = dt.date.fromisoformat(str(exp))
                days = (exp_date - now.date()).days
                if days > 0:
                    expiry_map[str(exp)] = days
            if not expiry_map:
                raise ValueError('No future expirations returned')
            chosen = sorted({min(expiry_map, key=lambda exp: (abs(expiry_map[exp] - target), expiry_map[exp])) for target in TARGETS})
            by_expiry = {}
            for exp in chosen:
                payload = api(session, '/markets/options/chains', {'symbol': symbol, 'expiration': exp, 'greeks': 'true'})
                options = (payload.get('options') or {}).get('option')
                chain = as_list(options)
                candidates = []
                for c in chain:
                    k, bid, ask = num(c.get('strike')), num(c.get('bid')), num(c.get('ask'))
                    kind = c.get('option_type')
                    if kind not in ('call', 'put') or k is None or bid is None or ask is None or bid <= 0 or ask < bid:
                        continue
                    mid = (bid + ask) / 2
                    # Filter obvious stale/wide quotes; threshold is a research choice.
                    if (ask - bid) / mid > 0.35:
                        continue
                    t = expiry_map[exp] / 365.25
                    approx_iv = implied_vol(spot, k, t, mid, args.rate, args.dividend_yield, kind)
                    greeks = c.get('greeks') or {}
                    vendor_iv = num(greeks.get('mid_iv')) or num(greeks.get('smv_vol'))
                    row = {
                        'snapshot_date_utc': snapshot_date, 'snapshot_timestamp_utc': now.isoformat(),
                        'symbol': symbol, 'expiration': exp, 'calendar_dte': expiry_map[exp],
                        'underlying_price': spot, 'option_symbol': c.get('symbol'),
                        'option_type': kind, 'strike': k, 'bid': bid, 'ask': ask, 'mid': mid,
                        'open_interest': c.get('open_interest'), 'volume': c.get('volume'),
                        'approx_bs_iv': approx_iv, 'vendor_iv_if_available': vendor_iv,
                        'assumed_rate': args.rate, 'assumed_dividend_yield': args.dividend_yield,
                        'source': 'tradier_sandbox_delayed',
                    }
                    candidates.append(row)
                # Nearest ATM call and put separately; retain raw audit rows.
                selected = []
                for kind in ('call', 'put'):
                    subset = [c for c in candidates if c['option_type'] == kind]
                    if subset:
                        selected.append(min(subset, key=lambda c: abs(c['strike'] - spot)))
                contract_rows.extend(selected)
                ivs = [c['approx_bs_iv'] for c in selected if c['approx_bs_iv'] is not None]
                by_expiry[exp] = sum(ivs) / len(ivs) if ivs else None
                time.sleep(args.pause)
            for target in TARGETS:
                exp = min(expiry_map, key=lambda e: (abs(expiry_map[e] - target), expiry_map[e]))
                summary_rows.append({
                    'snapshot_date_utc': snapshot_date, 'snapshot_timestamp_utc': now.isoformat(),
                    'symbol': symbol, 'target_calendar_dte': target, 'actual_expiration': exp,
                    'actual_calendar_dte': expiry_map[exp], 'underlying_price': spot,
                    'approx_atm_iv': by_expiry.get(exp), 'iv_method': 'BS_mid_ATM_call_put_mean',
                    'source': 'tradier_sandbox_delayed', 'assumed_rate': args.rate,
                    'assumed_dividend_yield': args.dividend_yield,
                    'note': 'Estimated IV; sandbox does not provide vendor Greeks/IV; NOT tenor-interpolated',
                })
            print(f'{symbol}: collected {len(chosen)} expirations; IV estimates may be blank')
        except Exception as exc:
            print(f'{symbol}: ERROR: {exc}', file=sys.stderr)
        time.sleep(args.pause)

    write_upsert(outdir / 'tradier_iv_snapshots.csv', summary_rows, ['snapshot_date_utc', 'symbol', 'target_calendar_dte'])
    write_upsert(outdir / 'tradier_iv_contracts.csv', contract_rows, ['snapshot_date_utc', 'symbol', 'option_symbol'])
    print(f'Saved {len(summary_rows)} target-horizon rows and {len(contract_rows)} ATM option quote rows to {outdir}')
    if not summary_rows:
        sys.exit(1)


if __name__ == '__main__':
    main()
