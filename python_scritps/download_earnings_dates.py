#!/usr/bin/env python3
"""
Download historical earnings dates for the symbols already present in
directional_excursions.csv.

Input
-----
directional_excursions.csv

Output
------
earnings_dates.csv
earnings_coverage.csv

Install
-------
See docs/SETUP.md for the shared dependency installation.

Run
---
python3 download_earnings_dates.py

Why separate this from the excursion generator?
-----------------------------------------------
The existing excursion dataset is expensive/useful and does not need to be
rebuilt. This script only obtains event dates. A later analysis step can join
each anchor_dt to the nearest previous/next earnings event and calculate DFE,
DTE, whether earnings falls inside each forward horizon, etc.

Important
---------
Yahoo/yfinance historical earnings coverage can vary by ticker and over time.
The coverage report is therefore part of the output and should be inspected
before using DTE/DFE results.
"""

from pathlib import Path
import pandas as pd
import argparse
from research_core.fetching import add_source_arguments, source_from_args
from research_core.errors import safe_error_code
from research_core.runtime import logged_main
from research_core.io import atomic_csv

INPUT = Path("directional_excursions.csv")
OUTPUT = Path("earnings_dates.csv")
COVERAGE = Path("earnings_coverage.csv")

# Ask for more history than we likely need. yfinance may cap what Yahoo returns.
EARNINGS_LIMIT = 100


def normalize_earnings_frame(symbol, frame):
    if frame is None or frame.empty:
        return pd.DataFrame()

    x = frame.copy().reset_index()

    # yfinance commonly names the index "Earnings Date", but tolerate changes.
    date_candidates = [
        "Earnings Date",
        "EarningsDate",
        "Date",
        "date",
        "index",
    ]

    date_col = None
    for c in date_candidates:
        if c in x.columns:
            date_col = c
            break

    if date_col is None:
        # Last-resort: first column after reset_index is normally the old index.
        date_col = x.columns[0]

    dt = pd.to_datetime(x[date_col], errors="coerce", utc=True)

    out = pd.DataFrame({
        "symbol": symbol,
        "earnings_datetime_utc": dt,
    })

    # Preserve useful Yahoo fields when available. These are NOT required for
    # the DTE/DFE study but are useful for audit/possible later research.
    optional = {
        "EPS Estimate": "eps_estimate",
        "Reported EPS": "reported_eps",
        "Surprise(%)": "surprise_pct",
    }

    for source, dest in optional.items():
        if source in x.columns:
            out[dest] = pd.to_numeric(x[source], errors="coerce")

    out = out.dropna(subset=["earnings_datetime_utc"]).copy()

    # Convert to a calendar date. For DTE/DFE we care primarily about the
    # trading-session event date. We retain the UTC timestamp as an audit field.
    out["earnings_date"] = out["earnings_datetime_utc"].dt.date

    # Yahoo can occasionally expose duplicate rows/dates.
    out = (
        out.sort_values("earnings_datetime_utc")
           .drop_duplicates(subset=["symbol", "earnings_date"], keep="last")
    )

    return out


@logged_main
def main(log):
    parser = add_source_arguments(argparse.ArgumentParser(description=__doc__))
    parser.add_argument('--input', type=Path, default=INPUT,
                        help='Directional excursion CSV; .csv.gz input is also supported.')
    parser.add_argument('--output', type=Path, default=OUTPUT, help='Derived earnings CSV path.')
    parser.add_argument('--coverage', type=Path, default=COVERAGE, help='Coverage CSV path.')
    args = parser.parse_args()
    source = source_from_args(args)
    if not args.input.exists():
        raise SystemExit('INPUT_NOT_FOUND: supply --input with the directional excursion CSV.')

    # Read only the columns needed to determine symbols and requested coverage.
    base = pd.read_csv(
        args.input,
        compression="infer",
        usecols=["symbol", "anchor_dt"],
        parse_dates=["anchor_dt"],
    )

    symbols = sorted(base["symbol"].dropna().astype(str).unique())

    requested_min = base.groupby("symbol")["anchor_dt"].min()
    requested_max = base.groupby("symbol")["anchor_dt"].max()

    log.message(f"Found {len(symbols)} symbols.")
    log.message(
        f"Anchor coverage: {base['anchor_dt'].min()} through {base['anchor_dt'].max()}"
    )

    all_events = []
    coverage_rows = []

    for i, symbol in enumerate(symbols, start=1):
        log.message(f"Processing earnings {i}/{len(symbols)}")

        status = "ok"
        error = ""

        try:
            frame = source.earnings(symbol, limit=EARNINGS_LIMIT)
            events = normalize_earnings_frame(symbol, frame)

        except Exception as exc:
            events = pd.DataFrame()
            status = "error"
            error = safe_error_code(exc)
            log.error(exc)

        if events.empty:
            if status == "ok":
                status = "empty"

            log.message(status)

            coverage_rows.append({
                "symbol": symbol,
                "status": status,
                "event_count": 0,
                "first_earnings_date": pd.NaT,
                "last_earnings_date": pd.NaT,
                "first_anchor_date": requested_min.get(symbol, pd.NaT),
                "last_anchor_date": requested_max.get(symbol, pd.NaT),
                "error": error,
            })

        else:
            all_events.append(events)

            first_event = pd.to_datetime(events["earnings_date"]).min()
            last_event = pd.to_datetime(events["earnings_date"]).max()

            log.message(
                f"{len(events):3d} events  "
                f"{first_event.date()} -> {last_event.date()}"
            )

            coverage_rows.append({
                "symbol": symbol,
                "status": status,
                "event_count": len(events),
                "first_earnings_date": first_event,
                "last_earnings_date": last_event,
                "first_anchor_date": requested_min.get(symbol, pd.NaT),
                "last_anchor_date": requested_max.get(symbol, pd.NaT),
                "error": error,
            })

        log.progress(success=status == "ok")

    coverage = pd.DataFrame(coverage_rows)
    atomic_csv(coverage, args.coverage, index=False)

    if not all_events:
        raise SystemExit(
            "No earnings dates were returned. The coverage CSV was still "
            "written; inspect it for Yahoo/yfinance errors."
        )

    earnings = pd.concat(all_events, ignore_index=True)

    cols = [
        "symbol",
        "earnings_date",
        "earnings_datetime_utc",
        "eps_estimate",
        "reported_eps",
        "surprise_pct",
    ]
    cols = [c for c in cols if c in earnings.columns]

    earnings = earnings[cols].sort_values(
        ["symbol", "earnings_date"]
    )

    atomic_csv(earnings, args.output, index=False)

    log.message("Output writing finished; run summary follows.")
    log.message(f"Earnings rows: {len(earnings):,}")
    log.message(f"Symbols with earnings: {earnings['symbol'].nunique()}")
    log.message(f"Wrote: {args.output}")
    log.message(f"Wrote: {args.coverage}")
    log.message(
        "\nIMPORTANT: Upload BOTH files. The coverage report tells us whether "
        "Yahoo supplied enough history for each stock; missing old earnings "
        "must not silently become false DTE/DFE observations."
    )


if __name__ == "__main__":
    raise SystemExit(main())
