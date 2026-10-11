#!/usr/bin/env python3
"""
Download historical earnings dates for the symbols already present in
directional_excursions.csv.gz.

Input
-----
directional_excursions.csv.gz

Output
------
earnings_dates.csv
earnings_coverage.csv

Install
-------
python3 -m pip install -U yfinance pandas

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
import time
import pandas as pd
import yfinance as yf

INPUT = Path("directional_excursions.csv.gz")
OUTPUT = Path("earnings_dates.csv")
COVERAGE = Path("earnings_coverage.csv")

# Ask for more history than we likely need. yfinance may cap what Yahoo returns.
EARNINGS_LIMIT = 100

# A short delay is intentionally conservative around Yahoo requests.
REQUEST_DELAY_SECONDS = 0.15


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


def main():
    if not INPUT.exists():
        raise SystemExit(
            f"Missing {INPUT}. Put this script in the same directory as "
            "directional_excursions.csv.gz, or edit INPUT at the top."
        )

    # Read only the columns needed to determine symbols and requested coverage.
    base = pd.read_csv(
        INPUT,
        compression="gzip",
        usecols=["symbol", "anchor_dt"],
        parse_dates=["anchor_dt"],
    )

    symbols = sorted(base["symbol"].dropna().astype(str).unique())

    requested_min = base.groupby("symbol")["anchor_dt"].min()
    requested_max = base.groupby("symbol")["anchor_dt"].max()

    print(f"Found {len(symbols)} symbols.")
    print(
        "Anchor coverage:",
        base["anchor_dt"].min(),
        "through",
        base["anchor_dt"].max(),
    )

    all_events = []
    coverage_rows = []

    for i, symbol in enumerate(symbols, start=1):
        print(f"[{i:02d}/{len(symbols):02d}] {symbol:6s}", end="  ")

        status = "ok"
        error = ""

        try:
            ticker = yf.Ticker(symbol)

            # Preferred yfinance interface for historical earnings events.
            frame = ticker.get_earnings_dates(limit=EARNINGS_LIMIT)
            events = normalize_earnings_frame(symbol, frame)

        except Exception as exc:
            events = pd.DataFrame()
            status = "error"
            error = repr(exc)

        if events.empty:
            if status == "ok":
                status = "empty"

            print(status)

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

            print(
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

        time.sleep(REQUEST_DELAY_SECONDS)

    coverage = pd.DataFrame(coverage_rows)
    coverage.to_csv(COVERAGE, index=False)

    if not all_events:
        raise SystemExit(
            "No earnings dates were returned. earnings_coverage.csv was still "
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

    earnings.to_csv(OUTPUT, index=False)

    print("\nDONE")
    print(f"Earnings rows: {len(earnings):,}")
    print(f"Symbols with earnings: {earnings['symbol'].nunique()}")
    print(f"Wrote: {OUTPUT}")
    print(f"Wrote: {COVERAGE}")
    print(
        "\nIMPORTANT: Upload BOTH files. The coverage report tells us whether "
        "Yahoo supplied enough history for each stock; missing old earnings "
        "must not silently become false DTE/DFE observations."
    )


if __name__ == "__main__":
    main()
