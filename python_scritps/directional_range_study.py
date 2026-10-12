#!/usr/bin/env python3
"""
Directional multi-horizon excursion study for U.S. equities.

Purpose
-------
Collect enough OHLCV data to test whether downside movement is statistically
larger/different than upside movement at H, D, and 1W..6W horizons.

Outputs
-------
directional_excursions.csv   One row per symbol/date/horizon
symbol_summary.csv           Per-symbol/horizon directional statistics
sector_summary.csv           Per-sector/horizon directional statistics
directional_universe.csv     Symbols/sectors actually requested

Install
-------
See docs/SETUP.md for the shared dependency installation.

Run
---
python3 directional_range_study.py

Notes
-----
* Daily history drives D and 1W..6W forward excursions.
* 60-minute history drives H. Yahoo intraday history is limited, so H has a
  shorter sample than D/weekly horizons.
* All forward measurements use information strictly AFTER the anchor close.
* ATR is backward-looking and shifted: no future bars enter normalization.
"""

import time
import numpy as np
import pandas as pd
import argparse
from research_core.fetching import add_source_arguments, source_from_args
from research_core.errors import safe_error_code
from research_core.runtime import logged_main
from research_core.io import atomic_csv

# 6 liquid/large names per GICS sector. Five are required; the sixth gives
# some resilience to download/history failures.
from research_core.universe import SECTORS

DAILY_PERIOD = "10y"
HOURLY_PERIOD = "700d"   # yfinance/Yahoo may return less; script tolerates it.
ATR_DAYS = 21
ATR_HOURS = 70
WEEK_HORIZONS = range(1, 7)


from research_core.prices import clean_ohlcv, true_range


def add_forward_excursions(df, symbol, sector, horizons, atr_len, unit):
    """
    Anchor = current bar close.
    Future window begins at next bar, preventing anchor-bar lookahead.

    MFE_up   = max future high - anchor close
    MAE_down = anchor close - min future low

    These are intentionally independent: a window can make both a large
    upside and downside excursion.
    """
    if df.empty:
        return []

    d = df.copy()
    d["TR"] = true_range(d)

    # Completed historical ATR only. At anchor t this uses TR through t-1.
    d["ATR"] = d["TR"].shift(1).rolling(atr_len, min_periods=atr_len).mean()

    rows = []
    n = len(d)

    for label, bars in horizons:
        if bars < 1:
            continue

        for i in range(atr_len, n - bars):
            anchor = float(d["Close"].iloc[i])
            atr = float(d["ATR"].iloc[i]) if pd.notna(d["ATR"].iloc[i]) else np.nan
            if not np.isfinite(anchor) or anchor <= 0 or not np.isfinite(atr) or atr <= 0:
                continue

            future = d.iloc[i + 1 : i + 1 + bars]
            if len(future) != bars:
                continue

            max_high = float(future["High"].max())
            min_low = float(future["Low"].min())
            end_close = float(future["Close"].iloc[-1])

            up = max(0.0, max_high - anchor)
            down = max(0.0, anchor - min_low)
            net = end_close - anchor

            # Time-to-extreme is useful for testing "drops are more aggressive".
            up_pos = int(np.argmax(future["High"].to_numpy())) + 1
            down_pos = int(np.argmin(future["Low"].to_numpy())) + 1

            rows.append(
                {
                    "symbol": symbol,
                    "sector": sector,
                    "anchor_dt": d.index[i],
                    "horizon": label,
                    "unit": unit,
                    "bars_forward": bars,
                    "anchor_close": anchor,
                    "atr": atr,
                    "max_future_high": max_high,
                    "min_future_low": min_low,
                    "end_close": end_close,
                    "up_excursion_$": up,
                    "down_excursion_$": down,
                    "up_excursion_pct": 100.0 * up / anchor,
                    "down_excursion_pct": 100.0 * down / anchor,
                    "up_excursion_atr": up / atr,
                    "down_excursion_atr": down / atr,
                    "net_change_pct": 100.0 * net / anchor,
                    "up_time_to_extreme": up_pos,
                    "down_time_to_extreme": down_pos,
                    "down_minus_up_atr": (down - up) / atr,
                    "down_up_ratio": down / up if up > 0 else np.nan,
                }
            )
    return rows


def summarize(g):
    up = g["up_excursion_atr"].dropna()
    dn = g["down_excursion_atr"].dropna()
    if len(g) == 0:
        return pd.Series(dtype=float)

    # Paired sign result: same anchor/window, which side had the larger excursion?
    paired = g[["up_excursion_atr", "down_excursion_atr"]].dropna()
    down_win = (paired["down_excursion_atr"] > paired["up_excursion_atr"]).mean()

    return pd.Series(
        {
            "n": len(g),
            "up_median_atr": up.median(),
            "down_median_atr": dn.median(),
            "up_p75_atr": up.quantile(0.75),
            "down_p75_atr": dn.quantile(0.75),
            "up_p90_atr": up.quantile(0.90),
            "down_p90_atr": dn.quantile(0.90),
            "up_p95_atr": up.quantile(0.95),
            "down_p95_atr": dn.quantile(0.95),
            "down_minus_up_median_atr": g["down_minus_up_atr"].median(),
            "pct_windows_down_larger": 100.0 * down_win,
            "median_up_time_to_extreme": g["up_time_to_extreme"].median(),
            "median_down_time_to_extreme": g["down_time_to_extreme"].median(),
            "median_net_change_pct": g["net_change_pct"].median(),
        }
    )


def download_one(symbol, interval, period, source, log):
    try:
        frame = source.history(symbol, period=period, interval=interval,
                               auto_adjust=True, actions=False)
        cleaned = clean_ohlcv(frame)
        log.progress(success=not cleaned.empty)
        return cleaned
    except Exception as exc:
        log.error(exc)
        log.progress(success=False)
        return pd.DataFrame()


@logged_main
def main(log):
    parser = add_source_arguments(argparse.ArgumentParser(description=__doc__))
    source = source_from_args(parser.parse_args())
    universe = pd.DataFrame(
        [(s, sec) for sec, syms in SECTORS.items() for s in syms],
        columns=["symbol", "sector"],
    )
    atomic_csv(universe, "directional_universe.csv", index=False)

    all_rows = []
    failures = []

    for sector, symbols in SECTORS.items():
        for symbol in symbols:
            log.message("Processing daily history")
            daily = download_one(symbol, "1d", DAILY_PERIOD, source, log)
            if daily.empty:
                failures.append((symbol, "1d"))
            else:
                horizons = [("D", 1)] + [(f"{w}W", 5 * w) for w in WEEK_HORIZONS]
                all_rows.extend(
                    add_forward_excursions(
                        daily, symbol, sector, horizons, ATR_DAYS, "daily bars"
                    )
                )

            log.message("Processing hourly history")
            hourly = download_one(symbol, "60m", HOURLY_PERIOD, source, log)
            if hourly.empty:
                failures.append((symbol, "60m"))
            else:
                # H means the next completed 60-minute bar.
                all_rows.extend(
                    add_forward_excursions(
                        hourly, symbol, sector, [("H", 1)], ATR_HOURS, "60m bars"
                    )
                )
            time.sleep(0.05)

    if not all_rows:
        raise SystemExit("No usable data downloaded.")

    raw = pd.DataFrame(all_rows)
    atomic_csv(raw, "directional_excursions.csv", index=False)

    symbol_summary = (
        raw.groupby(["sector", "symbol", "horizon"], observed=True)
        .apply(summarize, include_groups=False)
        .reset_index()
    )
    atomic_csv(symbol_summary, "symbol_summary.csv", index=False)

    sector_summary = (
        raw.groupby(["sector", "horizon"], observed=True)
        .apply(summarize, include_groups=False)
        .reset_index()
    )
    atomic_csv(sector_summary, "sector_summary.csv", index=False)

    log.message("Output writing finished; run summary follows.")
    log.message(f"Raw rows: {len(raw):,}")
    log.message(f"Symbols with data: {raw['symbol'].nunique()}")
    log.message("Files: directional_excursions.csv, symbol_summary.csv, sector_summary.csv, directional_universe.csv")
    if failures:
        log.message(f"Failed/empty histories: {len(failures)}")


if __name__ == "__main__":
    raise SystemExit(main())
