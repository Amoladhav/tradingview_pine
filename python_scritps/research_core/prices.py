"""Pure legacy OHLCV projections; capture occurs before this derived layer."""
import pandas as pd


def clean_ohlcv(frame, *, strip_timezone=False):
    if frame is None or frame.empty:
        return pd.DataFrame()
    data = frame.copy()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    required = ['Open', 'High', 'Low', 'Close', 'Volume']
    if not all(column in data.columns for column in required):
        return pd.DataFrame()
    data = data[required].dropna(subset=required[:4]).copy()
    data.index = pd.to_datetime(data.index)
    if strip_timezone:
        data.index = data.index.tz_localize(None)
    return data


def true_range(frame):
    previous_close = frame['Close'].shift(1)
    return pd.concat([frame['High'] - frame['Low'],
                      (frame['High'] - previous_close).abs(),
                      (frame['Low'] - previous_close).abs()], axis=1).max(axis=1)
