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
universe.csv                 Symbols/sectors actually requested

Install
-------
python3 -m pip install -U yfinance pandas numpy

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
import yfinance as yf

# 6 liquid/large names per GICS sector. Five are required; the sixth gives
# some resilience to download/history failures.
SECTORS = {
    "Communication Services": ["GOOGL", "META", "NFLX", "DIS", "TMUS", "VZ"],
    "Consumer Discretionary": ["AMZN", "TSLA", "HD", "MCD", "LOW", "NKE"],
    "Consumer Staples": ["WMT", "COST", "PG", "KO", "PEP", "PM"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC"],
    "Financials": ["JPM", "BAC", "WFC", "GS", "MS", "BLK"],
    "Health Care": ["LLY", "JNJ", "ABBV", "MRK", "UNH", "TMO"],
    "Industrials": ["GE", "CAT", "RTX", "UNP", "HON", "ETN"],
    "Information Technology": ["AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "AMD"],
    "Materials": ["LIN", "SHW", "FCX", "NEM", "APD", "ECL"],
    "Real Estate": ["PLD", "AMT", "EQIX", "WELL", "SPG", "O"],
    "Utilities": ["NEE", "SO", "DUK", "CEG", "AEP", "SRE"],
}

DAILY_PERIOD = "10y"
HOURLY_PERIOD = "700d"   # yfinance/Yahoo may return less; script tolerates it.
ATR_DAYS = 21
ATR_HOURS = 70
WEEK_HORIZONS = range(1, 7)


def clean_ohlcv(df):
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        # yf.download can produce a ticker level even for one ticker.
        df.columns = df.columns.get_level_values(0)
    need = ["Open", "High", "Low", "Close", "Volume"]
    if not all(c in df.columns for c in need):
        return pd.DataFrame()
    out = df[need].copy().dropna(subset=["Open", "High", "Low", "Close"])
    out.index = pd.to_datetime(out.index)
    return out


def true_range(df):
    prev_close = df["Close"].shift(1)
    return pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


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


def download_one(symbol, interval, period):
    try:
        df = yf.download(
            symbol,
            period=period,
            interval=interval,
            auto_adjust=True,
            actions=False,
            progress=False,
            threads=False,
        )
        return clean_ohlcv(df)
    except Exception as e:
        print(f"DOWNLOAD ERROR {symbol} {interval}: {e}")
        return pd.DataFrame()


def main():
    universe = pd.DataFrame(
        [(s, sec) for sec, syms in SECTORS.items() for s in syms],
        columns=["symbol", "sector"],
    )
    universe.to_csv("universe.csv", index=False)

    all_rows = []
    failures = []

    for sector, symbols in SECTORS.items():
        for symbol in symbols:
            print(f"{sector:25s} {symbol:6s} daily")
            daily = download_one(symbol, "1d", DAILY_PERIOD)
            if daily.empty:
                failures.append((symbol, "1d"))
            else:
                horizons = [("D", 1)] + [(f"{w}W", 5 * w) for w in WEEK_HORIZONS]
                all_rows.extend(
                    add_forward_excursions(
                        daily, symbol, sector, horizons, ATR_DAYS, "daily bars"
                    )
                )

            print(f"{sector:25s} {symbol:6s} hourly")
            hourly = download_one(symbol, "60m", HOURLY_PERIOD)
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
    raw.to_csv("directional_excursions.csv", index=False)

    symbol_summary = (
        raw.groupby(["sector", "symbol", "horizon"], observed=True)
        .apply(summarize, include_groups=False)
        .reset_index()
    )
    symbol_summary.to_csv("symbol_summary.csv", index=False)

    sector_summary = (
        raw.groupby(["sector", "horizon"], observed=True)
        .apply(summarize, include_groups=False)
        .reset_index()
    )
    sector_summary.to_csv("sector_summary.csv", index=False)

    print("\nDONE")
    print(f"Raw rows: {len(raw):,}")
    print(f"Symbols with data: {raw['symbol'].nunique()}")
    print("Files: directional_excursions.csv, symbol_summary.csv, sector_summary.csv, universe.csv")
    if failures:
        print("\nDownload failures/empty histories:")
        for x in failures:
            print("  ", x)


if __name__ == "__main__":
    main()
