"""Deterministic causal weekly features. No provider or filesystem access."""
from __future__ import annotations

import numpy as np
import pandas as pd

LAGS = (1, 2, 3, 4, 8)
WINDOWS = (2, 3, 4, 6, 8, 13)


def ratio(a, b):
    """Undefined divisions remain missing, including zero-volume observations."""
    return a / b.where(b != 0)


def rma(series: pd.Series, length: int) -> pd.Series:
    """Wilder smoothing seeded by the first length nonmissing observations.

    Missing observations do not advance the seed or state; output stays missing
    on those rows, avoiding imputed research observations.
    """
    if length < 1:
        raise ValueError("length must be positive")
    result = np.full(len(series), np.nan)
    seed: list[float] = []
    state = None
    for i, value in enumerate(series.to_numpy(dtype=float)):
        if not np.isfinite(value):
            continue
        if state is None:
            seed.append(value)
            if len(seed) == length:
                state = float(np.mean(seed))
        else:
            state += (value - state) / length
        if state is not None:
            result[i] = state
    return pd.Series(result, index=series.index)


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    up = rma(delta.clip(lower=0), length)
    down = rma(-delta.clip(upper=0), length)
    result = 100 - 100 / (1 + ratio(up, down))
    result = result.mask(up.eq(0), 0).mask(down.eq(0), 100)
    return result


def percentile(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).apply(lambda x: np.mean(x <= x[-1]), raw=True)


def weekly_bars(daily: pd.DataFrame, as_of: str) -> pd.DataFrame:
    """Observed US trading dates grouped Monday-Friday; no session imputation."""
    required = ["Open", "High", "Low", "Close", "Volume"]
    if not isinstance(daily.index, pd.DatetimeIndex) or daily.index.has_duplicates:
        raise ValueError("daily data requires unique DatetimeIndex")
    if not set(required).issubset(daily.columns):
        raise ValueError("daily OHLCV columns missing")
    data = daily.copy().sort_index()
    if data.index.tz is not None:
        data.index = data.index.tz_convert("America/New_York").tz_localize(None)
    data.index = data.index.normalize()
    if data.index.has_duplicates:
        raise ValueError("duplicate daily dates")
    if (data.index.weekday > 4).any():
        raise ValueError("non-US-session weekday")
    cutoff = pd.Timestamp(as_of).tz_localize(None).normalize()
    data = data.loc[data.index < cutoff]
    for field in required + (["Adj Close"] if "Adj Close" in data else []):
        values = pd.to_numeric(data[field], errors="coerce")
        invalid = data[field].notna() & (~np.isfinite(values) | values.isna())
        if invalid.any():
            raise ValueError("non-numeric or non-finite OHLCV")
        data[field] = values
    if (data[required].isna().any(axis=1)).any():
        raise ValueError("missing OHLCV; capture retained but symbol quarantined")
    if (data[["Open", "High", "Low", "Close"]] <= 0).any().any() or (data.Volume < 0).any():
        raise ValueError("unusable OHLCV; capture retained but symbol quarantined")
    if ((data.High < data[["Open", "Close", "Low"]].max(axis=1)) |
            (data.Low > data[["Open", "Close", "High"]].min(axis=1))).any():
        raise ValueError("inconsistent OHLC geometry")
    groups = data.resample("W-FRI")
    out = groups.agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
    out.columns = [x.lower() for x in out.columns]
    out["adjusted_close"] = groups["Adj Close"].agg(lambda x: x.iloc[-1] if len(x) else np.nan) if "Adj Close" in data else np.nan
    out["trading_days"] = groups.size()
    if out.trading_days.gt(5).any():
        raise ValueError("too many daily observations per week")
    # Missing whole weeks must not silently become adjacent observations.
    out["observed_week"] = out.trading_days.gt(0)
    ret = data.Close.pct_change(fill_method=None)
    detail = pd.DataFrame({"up": ret.gt(0), "down": ret.lt(0), "ret": ret,
                           "volume": data.Volume, "high": data.High, "low": data.Low})
    dg = detail.resample("W-FRI")
    out["daily_up_days"] = dg.up.sum()
    out["daily_down_days"] = dg.down.sum()
    out["daily_realized_volatility"] = dg.ret.std(ddof=1)
    out["daily_largest_up_return"] = detail.ret.where(detail.ret.gt(0)).resample("W-FRI").max()
    out["daily_largest_down_return"] = detail.ret.where(detail.ret.lt(0)).resample("W-FRI").min()
    for label, group in dg:
        if group.empty:
            continue
        out.loc[label, "daily_high_weekday"] = group.high.idxmax().weekday()
        out.loc[label, "daily_low_weekday"] = group.low.idxmin().weekday()
        for offset, (_, row) in enumerate(group.iterrows(), 1):
            out.loc[label, f"daily_volume_{offset}"] = row.volume
    out = out.loc[out.index < cutoff]
    if (~out.observed_week).any():
        raise ValueError("missing complete week; symbol quarantined")
    return out


def features(weekly: pd.DataFrame) -> pd.DataFrame:
    """All rolling windows include the current completed bar unless stated otherwise."""
    f = {name: weekly[name] for name in weekly}
    close, high, low, volume = (weekly[x] for x in ("close", "high", "low", "volume"))
    f["rsi_14"] = rsi(close)
    for n in (5, 8, 10, 14, 21):
        f[f"rsi_sma_{n}"] = f["rsi_14"].rolling(n).mean()
    rs, ma = f["rsi_14"], f["rsi_sma_14"]
    spread = rs - ma
    f["spread"] = spread
    f["absolute_spread"] = spread.abs()
    bull = spread.gt(0) & spread.shift().le(0)
    bear = spread.lt(0) & spread.shift().ge(0)
    f["cross_direction"] = pd.Series(np.select([bull, bear], [1, -1], default=0), index=close.index)
    cross = bull | bear
    positions = pd.Series(np.arange(len(close), dtype=float), index=close.index)
    last_cross = positions.where(cross).ffill().shift()
    f["weeks_since_previous_cross"] = positions - last_cross
    f["max_absolute_spread_since_previous_cross"] = spread.abs().groupby(cross.cumsum()).cummax().shift().where(last_cross.notna())
    side = np.sign(spread)
    runs = side.ne(side.shift()).cumsum()
    f["weeks_on_previous_side"] = side.groupby(runs).cumcount().add(1).shift().where(side.shift().ne(0))
    for n in (1, 2, 3, 4, 6, 8):
        f[f"spread_previous_{n}"] = spread.shift(n)
    f["spread_slope"] = spread.diff()
    for n in (4, 8, 13, 26):
        f[f"crosses_prior_{n}"] = cross.shift().rolling(n).sum()
    for prefix, series in (("rsi", rs), ("rsi_sma", ma), ("price", close)):
        for n in LAGS:
            f[f"{prefix}_previous_{n}"] = series.shift(n)
            f[f"{prefix}_change_{n}"] = series.diff(n)
        for n in WINDOWS:
            x = np.arange(n) - (n - 1) / 2
            endpoint = series.diff(n - 1) / (n - 1)
            ols = series.rolling(n).apply(lambda y, x=x: np.dot(x, y) / np.dot(x, x), raw=True)
            for kind, slope in (("endpoint", endpoint), ("ols", ols)):
                key = f"{prefix}_{kind}_slope_{n}"
                f[key] = slope
                f[key + "_change"] = slope.diff()
                f[key + "_strengthening"] = slope.abs().gt(slope.shift().abs()).where(slope.notna() & slope.shift().notna())
                if prefix == "price":
                    f[key + "_normalized"] = ratio(slope, close)
        for n in (4, 8, 13, 26):
            f[f"{prefix}_minimum_{n}"] = series.rolling(n).min()
            f[f"{prefix}_maximum_{n}"] = series.rolling(n).max()
            f[f"{prefix}_range_{n}"] = f[f"{prefix}_maximum_{n}"] - f[f"{prefix}_minimum_{n}"]
        # One bar each side; at t only pivot t-1 can be confirmed.
        for kind, compare in (("low", "lt"), ("high", "gt")):
            pivot = getattr(series.shift(), compare)(series.shift(2)) & getattr(series.shift(), compare)(series)
            value = series.shift().where(pivot)
            latest = value.ffill()
            previous = value.dropna().shift().reindex(series.index).ffill()
            f[f"{prefix}_pivot_{kind}"] = latest
            f[f"{prefix}_previous_pivot_{kind}"] = previous
            f[f"{prefix}_pivot_{kind}_change"] = latest - previous
            f[f"{prefix}_pivot_{kind}_higher"] = latest.gt(previous).where(previous.notna())
            f[f"{prefix}_pivot_{kind}_lower"] = latest.lt(previous).where(previous.notna())
    slope = ma.diff()
    sign_change = np.sign(slope).ne(np.sign(slope.shift())) & slope.notna() & slope.shift().notna()
    f["sma_slope_sign_changed"] = sign_change
    f["weeks_since_sma_slope_sign_change"] = positions - positions.where(sign_change).ffill()
    for n in WINDOWS:
        f[f"cross_velocity_{n}"] = (f[f"rsi_ols_slope_{n}"] - f[f"rsi_sma_ols_slope_{n}"]) / 100
    f["rsi_below_20"] = rs.lt(20).where(rs.notna())
    f["rsi_above_80"] = rs.gt(80).where(rs.notna())
    for a, b in ((20,30),(30,40),(40,45),(45,50),(50,55),(55,60),(60,70),(70,80)):
        f[f"rsi_zone_{a}_{b}"] = rs.between(a,b).where(rs.notna())
    for n in (30, 40, 50, 60, 70):
        f[f"rsi_distance_{n}"] = rs - n
    for n in (4, 8, 13, 26):
        f[f"rsi_percentile_{n}"] = percentile(rs, n)
        f[f"weeks_since_rsi_minimum_{n}"] = rs.rolling(n).apply(lambda x: np.argmin(x[::-1]), raw=True)
        f[f"weeks_since_rsi_maximum_{n}"] = rs.rolling(n).apply(lambda x: np.argmax(x[::-1]), raw=True)
    for n in (1, 2, 4, 8, 13, 26, 52):
        f[f"return_{n}"] = close.pct_change(n, fill_method=None)
    f["weekly_return"] = f["return_1"]
    for n in (4, 13, 26, 52):
        hh, ll = high.rolling(n).max(), low.rolling(n).min()
        f[f"distance_high_{n}"] = ratio(close, hh) - 1
        f[f"distance_low_{n}"] = ratio(close, ll) - 1
        for name, value in (("high", hh), ("low", ll)):
            f[f"price_{name}_change_{n}"] = value.diff()
    for n in (10, 20, 40, 50):
        pma = close.rolling(n).mean()
        f[f"price_sma_{n}"] = pma
        f[f"price_relative_sma_{n}"] = ratio(close, pma) - 1
        f[f"price_sma_slope_{n}"] = pma.diff()
        f[f"price_sma_slope_change_{n}"] = pma.diff().diff()
    tr = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    f["true_range"] = tr
    for n in (5, 14, 21):
        atr = rma(tr, n)
        f[f"atr_{n}"] = atr
        f[f"atr_percent_{n}"] = 100 * ratio(atr, close)
        f[f"atr_expansion_{n}"] = ratio(atr, atr.shift().rolling(n).mean())
    for n in (4, 8, 13, 26, 52):
        vol = f["return_1"].rolling(n).std(ddof=1) * np.sqrt(52)
        f[f"realized_volatility_{n}"] = vol
        f[f"realized_volatility_ratio_{n}"] = ratio(vol, vol.shift())
    for n in (52, 104, 156):
        f[f"volatility_percentile_{n}"] = percentile(f["realized_volatility_13"], n)
    for n in (4, 13, 26, 52):
        average = volume.rolling(n).mean()
        f[f"volume_average_{n}"] = average
        f[f"relative_volume_{n}"] = ratio(volume, average)
    for n in (26, 52, 104):
        f[f"volume_percentile_{n}"] = percentile(volume, n)
    median = volume.rolling(26).median()
    mad = volume.rolling(26).apply(lambda x: np.median(np.abs(x-np.median(x))), raw=True)
    f["volume_robust_zscore_26"] = ratio(volume-median, 1.4826*mad)
    for n in (1,2,3,4):
        f[f"volume_previous_{n}"] = volume.shift(n)
        f[f"relative_volume_13_previous_{n}"] = f["relative_volume_13"].shift(n)
    for name, value in (("price_change", close.diff()), ("absolute_price_change", close.diff().abs()), ("true_range", tr)):
        f[name + "_per_volume"] = ratio(value, volume)
        f[name + "_atr_per_relative_volume"] = ratio(ratio(value, f["atr_14"]), f["relative_volume_13"])
    body, span = close-weekly.open, high-low
    f.update(body=body, absolute_body=body.abs(), candle_range=span,
             upper_wick=high-pd.concat([close,weekly.open],axis=1).max(axis=1),
             lower_wick=pd.concat([close,weekly.open],axis=1).min(axis=1)-low,
             gap=weekly.open-close.shift())
    for key in ("body", "upper_wick", "lower_wick"):
        f[key + "_fraction_range"] = ratio(f[key], span)
    f["close_location"] = ratio(close-low, span)
    f["directional_efficiency"] = ratio(body.abs(), span)
    f["body_atr"] = ratio(body, f["atr_14"])
    f["range_atr"] = ratio(span, f["atr_14"])
    f["return_atr"] = ratio(close.diff(), f["atr_14"])
    f["body_atr_times_relative_volume"] = f["body_atr"] * f["relative_volume_13"]
    return pd.DataFrame(f, index=weekly.index)
