# Intraday range research collector

This is a **data collector**, not a validated forecasting model. It saves regular-trading-hours OHLCV and a manifest. It never fabricates hourly outcomes or extrapolates daily models.

## Install

```bash
python -m pip install -r requirements.txt
```

## Test SOXL first

```bash
python collect_intraday.py --only SOXL --interval 30m --out intraday_30m
```

## Collect research basket

```bash
python collect_intraday.py --interval 30m --out intraday_30m
```

## Longer historical coverage (coarser bars)

```bash
python collect_intraday.py --interval 60m --out intraday_60m
```

## Important limitations

- Yahoo/yfinance documents a ~60-day limit for 30-minute bars; 60-minute bars can cover ~730 days, subject to provider availability. No request can bypass retention limits.
- Yahoo's 30-minute implementation may fetch 15-minute bars and resample internally.
- Data is restricted to regular US trading hours, 09:30–16:00 Eastern, excluding extended hours.
- Timestamps identify **bar starts**. Do not include unfinished live bars in a backtest.
- The 60-minute feed may produce six full hours plus a final partial hour. This is why the script preserves timestamps instead of pretending every session has seven equal hours.
- `auto_adjust=False` preserves provider OHLC price scale; stock splits and distribution adjustments require separate verification. Never mix adjusted close with unadjusted high/low.
- The manifest reports missing/incomplete sessions. Half-days and halts require review, not blanket removal.
- No options/IV data is needed to start price-range validation.
- Historical validation must calculate forward labels only within the same trading session and use chronological train/test splits, plus block/non-overlap uncertainty estimates.
- `--only` bypasses all universe discovery and Tradier. No Wikipedia dependency.

Output: one `SYMBOL_INTERVAL_ohlcv.csv.gz` per ticker, `manifest.csv`, and `collection_metadata.json`.

Upload the output folder as a ZIP. We can then test 30m / 60m expiry-day ranges, including SOXL, without inventing sub-day performance claims.
