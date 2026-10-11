#!/usr/bin/env python3
"""
Build an enhanced daily research dataset for adaptive X-day price-range modeling.

GOAL
----
For a broad stock universe, create one row per symbol / anchor date / forward
horizon X (1..60 trading days), containing:

1) Outcomes known only AFTER the anchor (training targets):
   - terminal return at X
   - maximum upside excursion during X
   - maximum downside excursion during X
   - all outcomes normalized by anchor price and completed historical ATR

2) State features known AT the anchor only:
   - ATR / realized-volatility state
   - trend and directional efficiency
   - recent price structure / range location
   - candle body / wick behavior
   - gap behavior
   - volume participation
   - prior proximity to the current price zone

NO earnings data is joined here. We already have earnings_dates.csv and will
join earnings state during analysis. Keeping it separate makes auditing easier.

OUTPUT
------
adaptive_range_daily.csv.gz
adaptive_range_symbols.csv

INSTALL
-------
python3 -m pip install -U yfinance pandas numpy

RUN
---
python3 build_adaptive_range_dataset.py

DESIGN NOTES
------------
* Daily bars only in this stage. This targets D through ~60 trading days.
* H/intraday should be modeled separately; mixing hourly and daily state
  features would complicate interpretation.
* auto_adjust=True keeps price history internally consistent through splits.
* Every rolling feature is shifted by one bar where necessary so the feature
  represents information completed BEFORE the anchor bar, except explicitly
  named anchor-candle features, which use the completed anchor candle.
* Forward outcomes begin with the NEXT trading bar.
"""

from pathlib import Path
import time
import numpy as np
import pandas as pd
import yfinance as yf

# Same broad 66-stock / 11-sector universe used in the earlier study.
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

PERIOD = "10y"
MAX_X = 60
ATR_LEN = 21
MIN_HISTORY = 126


def clean(df):
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    need = ["Open", "High", "Low", "Close", "Volume"]
    if not all(c in df.columns for c in need):
        return pd.DataFrame()
    d = df[need].copy()
    d.index = pd.to_datetime(d.index).tz_localize(None)
    return d.dropna(subset=["Open", "High", "Low", "Close"])


def true_range(d):
    pc = d["Close"].shift(1)
    return pd.concat([
        d["High"] - d["Low"],
        (d["High"] - pc).abs(),
        (d["Low"] - pc).abs(),
    ], axis=1).max(axis=1)


def rolling_slope_norm(close, window):
    """
    Cheap Pine-reproducible normalized linear slope proxy:
    change over window divided by mean price and window length.
    """
    return (close - close.shift(window)) / close.shift(window) / window


def directional_efficiency(close, window):
    net = (close - close.shift(window)).abs()
    path = close.diff().abs().rolling(window).sum()
    return net / path.replace(0, np.nan)


def signed_efficiency(close, window):
    direction = np.sign(close - close.shift(window))
    return direction * directional_efficiency(close, window)


def prepare_features(d):
    x = d.copy()

    x["tr"] = true_range(x)

    # Completed-history ATR at the anchor. The anchor candle itself is not in
    # this ATR estimate, matching our earlier defensive/no-leak convention.
    x["atr21"] = x["tr"].shift(1).rolling(ATR_LEN).mean()
    x["atr5"] = x["tr"].shift(1).rolling(5).mean()
    x["atr63"] = x["tr"].shift(1).rolling(63).mean()

    x["atr5_atr21"] = x["atr5"] / x["atr21"]
    x["atr21_atr63"] = x["atr21"] / x["atr63"]

    # Close-to-close realized volatility. Annualization is irrelevant for the
    # ratios but useful for interpretable standalone values.
    lr = np.log(x["Close"] / x["Close"].shift(1))
    x["rv5"] = lr.shift(1).rolling(5).std() * np.sqrt(252)
    x["rv21"] = lr.shift(1).rolling(21).std() * np.sqrt(252)
    x["rv63"] = lr.shift(1).rolling(63).std() * np.sqrt(252)
    x["rv5_rv21"] = x["rv5"] / x["rv21"]
    x["rv21_rv63"] = x["rv21"] / x["rv63"]

    # Trend / directional state at multiple scales.
    for w in (5, 10, 20, 40, 60):
        x[f"slope_{w}"] = rolling_slope_norm(x["Close"], w)
        x[f"eff_{w}"] = directional_efficiency(x["Close"], w)
        x[f"signed_eff_{w}"] = signed_efficiency(x["Close"], w)

    # Position in recent price ranges. Uses the completed anchor candle and
    # therefore is valid for a prediction made after that candle closes.
    for w in (10, 20, 60, 126):
        lo = x["Low"].rolling(w).min()
        hi = x["High"].rolling(w).max()
        width = (hi - lo).replace(0, np.nan)
        x[f"range_pos_{w}"] = (x["Close"] - lo) / width
        x[f"range_width_atr_{w}"] = width / x["atr21"]

    # Anchor candle geometry.
    candle_range = (x["High"] - x["Low"]).replace(0, np.nan)
    body = x["Close"] - x["Open"]
    x["body_atr"] = body / x["atr21"]
    x["body_fraction"] = body / candle_range
    x["upper_wick_fraction"] = (
        x["High"] - x[["Open", "Close"]].max(axis=1)
    ) / candle_range
    x["lower_wick_fraction"] = (
        x[["Open", "Close"]].min(axis=1) - x["Low"]
    ) / candle_range
    x["anchor_tr_atr"] = x["tr"] / x["atr21"]

    # Gap state.
    prev_close = x["Close"].shift(1)
    x["gap_atr"] = (x["Open"] - prev_close) / x["atr21"]
    x["abs_gap_atr"] = x["gap_atr"].abs()
    x["gap5_mean_abs_atr"] = x["abs_gap_atr"].shift(1).rolling(5).mean()
    x["gap20_max_abs_atr"] = x["abs_gap_atr"].shift(1).rolling(20).max()

    # Volume state. Dollar volume helps normalize raw-share-volume differences.
    vol20 = x["Volume"].shift(1).rolling(20).median()
    vol63 = x["Volume"].shift(1).rolling(63).median()
    x["volume_rel20"] = x["Volume"] / vol20.replace(0, np.nan)
    x["volume_med20_med63"] = vol20 / vol63.replace(0, np.nan)

    dollar_vol = x["Close"] * x["Volume"]
    dv20 = dollar_vol.shift(1).rolling(20).median()
    x["dollar_volume_rel20"] = dollar_vol / dv20.replace(0, np.nan)

    # Price-zone memory: how often recent closes were within +/- 1 ATR21 of the
    # current close. This is a cheap approximation to "has price spent time
    # around here before?" and is Pine-reproducible without pattern search.
    closes = x["Close"].to_numpy(dtype=float)
    atr = x["atr21"].to_numpy(dtype=float)
    zone_count_60 = np.full(len(x), np.nan)
    zone_count_126 = np.full(len(x), np.nan)

    for i in range(len(x)):
        if not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        for w, dest in ((60, zone_count_60), (126, zone_count_126)):
            start = max(0, i - w)
            hist = closes[start:i]  # exclude anchor itself
            if len(hist) < min(20, w):
                continue
            dest[i] = np.mean(np.abs(hist - closes[i]) <= atr[i])

    x["price_zone_hit_rate_60"] = zone_count_60
    x["price_zone_hit_rate_126"] = zone_count_126

    return x


FEATURE_COLUMNS = [
    "atr21", "atr5_atr21", "atr21_atr63",
    "rv5", "rv21", "rv63", "rv5_rv21", "rv21_rv63",
    "slope_5", "slope_10", "slope_20", "slope_40", "slope_60",
    "eff_5", "eff_10", "eff_20", "eff_40", "eff_60",
    "signed_eff_5", "signed_eff_10", "signed_eff_20",
    "signed_eff_40", "signed_eff_60",
    "range_pos_10", "range_pos_20", "range_pos_60", "range_pos_126",
    "range_width_atr_10", "range_width_atr_20",
    "range_width_atr_60", "range_width_atr_126",
    "body_atr", "body_fraction",
    "upper_wick_fraction", "lower_wick_fraction",
    "anchor_tr_atr",
    "gap_atr", "abs_gap_atr", "gap5_mean_abs_atr", "gap20_max_abs_atr",
    "volume_rel20", "volume_med20_med63", "dollar_volume_rel20",
    "price_zone_hit_rate_60", "price_zone_hit_rate_126",
]



ANCHOR_OUTPUT = Path("adaptive_range_anchors.parquet")
OUTCOME_OUTPUT = Path("adaptive_range_outcomes.parquet")
SYMBOL_OUTPUT = Path("adaptive_range_symbols.csv")

def build_symbol_tables(d, symbol, sector):
    """
    Returns two compact tables for ONE symbol only.

    anchors:
      one row per symbol/date containing state features.

    outcomes:
      one row per symbol/date/X containing only prediction targets.

    The large state vector is therefore not duplicated 60 times.
    """
    f = prepare_features(d)
    anchor_rows = []
    outcome_rows = []
    n = len(f)

    for i in range(MIN_HISTORY, n - MAX_X):
        a = f.iloc[i]
        price = float(a["Close"])
        atr = float(a["atr21"])

        if not np.isfinite(price) or price <= 0 or not np.isfinite(atr) or atr <= 0:
            continue
        if not np.isfinite(a["rv21"]) or not np.isfinite(a["signed_eff_20"]):
            continue

        anchor = {
            "symbol": symbol,
            "sector": sector,
            "anchor_dt": f.index[i],
            "anchor_close": price,
        }
        for col in FEATURE_COLUMNS:
            anchor[col] = a.get(col, np.nan)
        anchor_rows.append(anchor)

        future = f.iloc[i + 1:i + 1 + MAX_X]
        highs = future["High"].to_numpy(dtype=np.float64)
        lows = future["Low"].to_numpy(dtype=np.float64)
        closes = future["Close"].to_numpy(dtype=np.float64)

        cum_high = np.maximum.accumulate(highs)
        cum_low = np.minimum.accumulate(lows)

        # Only compact outcome columns are repeated across X=1..60.
        for j in range(MAX_X):
            X = j + 1
            end_close = closes[j]
            max_high = cum_high[j]
            min_low = cum_low[j]

            terminal = end_close - price
            up_terminal = max(0.0, terminal)
            down_terminal = max(0.0, -terminal)
            up_exc = max(0.0, max_high - price)
            down_exc = max(0.0, price - min_low)

            outcome_rows.append({
                "symbol": symbol,
                "anchor_dt": f.index[i],
                "x_days": X,
                "end_close": end_close,
                "terminal_return_atr": terminal / atr,
                "terminal_return_pct": 100.0 * terminal / price,
                "up_terminal_atr": up_terminal / atr,
                "down_terminal_atr": down_terminal / atr,
                "up_excursion_atr": up_exc / atr,
                "down_excursion_atr": down_exc / atr,
                "up_excursion_pct": 100.0 * up_exc / price,
                "down_excursion_pct": 100.0 * down_exc / price,
            })

    anchors = pd.DataFrame(anchor_rows)
    outcomes = pd.DataFrame(outcome_rows)

    for frame in (anchors, outcomes):
        for c in frame.select_dtypes(include=["float64"]).columns:
            frame[c] = pd.to_numeric(frame[c], downcast="float")
        if "x_days" in frame.columns:
            frame["x_days"] = pd.to_numeric(frame["x_days"], downcast="integer")

    return anchors, outcomes


def write_parquet_piece(frame, root, symbol):
    """
    Write one symbol to its own Parquet file.

    This is intentionally simple rather than relying on a single ParquetWriter:
    individual files are easy to inspect, replace, retry, and read as a dataset.
    """
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{symbol}.parquet"
    frame.to_parquet(
        path,
        engine="pyarrow",
        compression="zstd",
        index=False,
    )
    return path


def main():
    try:
        import pyarrow  # noqa: F401
    except ImportError:
        raise SystemExit(
            "This streaming version requires pyarrow.\n"
            "Install with:\n"
            "  python3 -m pip install -U yfinance pandas numpy pyarrow"
        )

    # Outputs are directories containing one Parquet file per symbol.
    anchor_root = Path("adaptive_range_anchors")
    outcome_root = Path("adaptive_range_outcomes")

    anchor_root.mkdir(exist_ok=True)
    outcome_root.mkdir(exist_ok=True)

    status = []

    for sector, symbols in SECTORS.items():
        for symbol in symbols:
            print(f"{sector:25s} {symbol:6s}", end="  ", flush=True)

            try:
                raw = yf.download(
                    symbol,
                    period=PERIOD,
                    interval="1d",
                    auto_adjust=True,
                    actions=False,
                    progress=False,
                    threads=False,
                )
                d = clean(raw)

                if d.empty or len(d) < MIN_HISTORY + MAX_X + 10:
                    print("insufficient history")
                    status.append({
                        "symbol": symbol,
                        "sector": sector,
                        "status": "insufficient",
                        "daily_bars": len(d),
                    })
                    continue

                anchors, outcomes = build_symbol_tables(d, symbol, sector)

                if anchors.empty or outcomes.empty:
                    print("no model rows")
                    status.append({
                        "symbol": symbol,
                        "sector": sector,
                        "status": "empty",
                        "daily_bars": len(d),
                    })
                    continue

                anchor_path = write_parquet_piece(
                    anchors, anchor_root, symbol
                )
                outcome_path = write_parquet_piece(
                    outcomes, outcome_root, symbol
                )

                print(
                    f"{len(d):,} bars -> "
                    f"{len(anchors):,} anchors / "
                    f"{len(outcomes):,} outcomes"
                )

                status.append({
                    "symbol": symbol,
                    "sector": sector,
                    "status": "ok",
                    "daily_bars": len(d),
                    "anchor_rows": len(anchors),
                    "outcome_rows": len(outcomes),
                    "first_date": d.index.min(),
                    "last_date": d.index.max(),
                    "anchor_file": str(anchor_path),
                    "outcome_file": str(outcome_path),
                })

                # Explicitly release this symbol before downloading the next.
                del anchors
                del outcomes
                del d
                del raw

            except Exception as exc:
                print(f"ERROR {exc}")
                status.append({
                    "symbol": symbol,
                    "sector": sector,
                    "status": "error",
                    "error": repr(exc),
                })

            # Rewrite audit after every symbol so an interrupted run still has
            # useful progress information.
            pd.DataFrame(status).to_csv(SYMBOL_OUTPUT, index=False)
            time.sleep(0.05)

    audit = pd.DataFrame(status)
    audit.to_csv(SYMBOL_OUTPUT, index=False)

    ok = audit[audit["status"] == "ok"] if not audit.empty else pd.DataFrame()

    print("\nDONE")
    print(f"Successful symbols: {len(ok)}")
    if not ok.empty:
        print(f"Anchor rows: {int(ok['anchor_rows'].sum()):,}")
        print(f"Outcome rows: {int(ok['outcome_rows'].sum()):,}")
    print(f"Anchor dataset directory: {anchor_root}/")
    print(f"Outcome dataset directory: {outcome_root}/")
    print(f"Audit: {SYMBOL_OUTPUT}")
    print("\nFor upload, archive the two directories:")
    print("  tar -czf adaptive_range_anchors.tar.gz adaptive_range_anchors/")
    print("  tar -czf adaptive_range_outcomes.tar.gz adaptive_range_outcomes/")


if __name__ == "__main__":
    main()
