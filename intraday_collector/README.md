# Intraday range research collector

This is a **data collector**, not a validated forecasting model. It saves regular-trading-hours OHLCV and a manifest. It never fabricates hourly outcomes or extrapolates daily models.

## Setup and execution

Follow the shared repository [setup guide](../docs/SETUP.md). The directory
requirements file delegates to the root requirements. Run from the repository root:

```bash
python intraday_collector/collect_intraday.py --only SOXL --interval 30m --out intraday_30m --fetch
python intraday_collector/collect_intraday.py --only SOXL --interval 30m --out intraday_replay
python intraday_collector/collect_intraday.py --interval 60m --out intraday_60m --fetch
```

The default uses exact-request cached captures only. `--fetch` explicitly enables
public Yahoo fetching; `--cache-dir` changes private cache storage. The shared
adapter preserves the complete decoded yfinance table before normalization,
regular-session filtering, deduplication or invalid-row removal. This is the
library capture boundary, not raw wire data. Output OHLCV is a derived dataset.

Retry count remains bounded (`--retries 0..10`, default 2); cache misses are not
retried. `--pause` controls pacing between public symbol fetches. Failures use safe
codes, and partial/all-failed runs exit nonzero. Shared progress and sanitized run
reports are written under `artifacts/`. Per-symbol output and manifest replacement
is atomic; prior run logs and captures are retained.

## Important limitations

- Defaults request 59 days for 30-minute bars and 720 days for 60-minute bars. Provider retention can change; live coverage is unverified and requests cannot bypass limits.
- Yahoo's 30-minute implementation may fetch 15-minute bars and resample internally.
- Data is restricted to regular US trading hours, 09:30–16:00 Eastern, excluding extended hours.
- Timestamps identify **bar starts**. Do not include unfinished live bars in a backtest.
- The 60-minute feed may produce six full hours plus a final partial hour. This is why the script preserves timestamps instead of pretending every session has seven equal hours.
- `auto_adjust=False` preserves provider OHLC price scale; stock splits and distribution adjustments require separate verification. Never mix adjusted close with unadjusted high/low.
- The manifest counts observed sessions with fewer than 13 (30m) or 7 (60m) bars; it cannot detect wholly absent trading days without an exchange calendar. Half-days and halts require review, not blanket removal.
- No options/IV data is needed to start price-range validation.
- Historical validation must calculate forward labels only within the same trading session and use chronological train/test splits, plus block/non-overlap uncertainty estimates.
- `--only` bypasses all universe discovery and Tradier. No Wikipedia dependency.

Output: one `SYMBOL_INTERVAL_ohlcv.csv.gz` per ticker, `manifest.csv`, and `collection_metadata.json`.

Synthetic offline checks cover regular-session filtering across a DST transition,
deduplication, timezone-naive rejection, invalid OHLCV filtering and provider request
settings. Live fetching, holidays/early closes, unfinished-bar handling and native
Windows, WSL, Ubuntu and macOS acceptance remain pending. Existing outputs are merged
by timestamp, with the new observation winning; historical files from other price
adjustment settings must not be mixed. No exchange calendar or session-completeness
proof has been added.
