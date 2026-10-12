"""Future-only outcome/path tables; never joined back into predictors."""
from __future__ import annotations

import numpy as np
import pandas as pd

HORIZONS = (1, 2, 3, 4, 6, 8, 13, 26, 39, 52)


def event_id(symbol, date):
    return f"{symbol}:{date:%Y-%m-%d}:rsi14-sma14-v1"


def outcomes(frame, symbol):
    rows, paths = [], []
    events = np.flatnonzero(frame.cross_direction.to_numpy())
    next_opposite = {}
    next_by_direction = {}
    for pos in reversed(events):
        direction = frame.cross_direction.iloc[pos]
        next_opposite[pos] = next_by_direction.get(-direction)
        next_by_direction[direction] = pos
    for pos in events:
        event = frame.iloc[pos]
        key = event_id(symbol, frame.index[pos])
        base, atr, direction = event.close, event.atr_14, event.cross_direction
        row = {"event_id": key, "available_future_weeks": len(frame)-pos-1}
        for n in HORIZONS:
            future = frame.iloc[pos+1:pos+n+1]
            complete = len(future) == n
            row[f"complete_{n}"] = complete
            for name in ("return", "highest_high", "lowest_low", "weeks_to_high", "weeks_to_low", "mfe", "mae", "mfe_atr", "mae_atr"):
                row[f"{name}_{n}"] = np.nan
            if not complete:
                continue
            hh, ll = future.high.max(), future.low.min()
            favorable = max(0, hh-base) if direction == 1 else max(0, base-ll)
            adverse = min(0, ll-base) if direction == 1 else min(0, base-hh)
            row.update({f"return_{n}": future.close.iloc[-1]/base-1,
                        f"highest_high_{n}": hh, f"lowest_low_{n}": ll,
                        f"weeks_to_high_{n}": int(np.argmax(future.high.to_numpy()))+1,
                        f"weeks_to_low_{n}": int(np.argmin(future.low.to_numpy()))+1,
                        f"mfe_{n}": favorable/base, f"mae_{n}": adverse/base,
                        f"mfe_atr_{n}": favorable/atr if atr > 0 else np.nan,
                        f"mae_atr_{n}": adverse/atr if atr > 0 else np.nan})
        opposite = next_opposite[pos]
        has_opposite = opposite is not None
        end = opposite if has_opposite else len(frame)-1
        row["next_opposite_observed"] = has_opposite
        row["weeks_until_next_opposite"] = end-pos if has_opposite else np.nan
        row["return_at_next_opposite"] = frame.close.iloc[end]/base-1 if has_opposite else np.nan
        # Ending opposite-cross bar is included; no entry/execution claim is made.
        segment = frame.iloc[pos+1:end+1]
        favorable = (segment.high.max()-base) if direction == 1 else (base-segment.low.min())
        adverse = (segment.low.min()-base) if direction == 1 else (base-segment.high.max())
        row["directional_move_before_opposite"] = max(0, favorable)/base if has_opposite else np.nan
        row["adverse_move_before_opposite"] = min(0, adverse)/base if has_opposite else np.nan
        future = frame.iloc[pos+1:pos+53]
        row["path_complete_52"] = len(future) == 52
        for level in (.5, 1, 1.5, 2, 3, 4):
            for sign in (1, -1):
                hits = np.flatnonzero((future.high >= base+level*atr) if sign == 1 else (future.low <= base-level*atr)) if atr > 0 else []
                row[f"first_hit_{'plus' if sign == 1 else 'minus'}_{str(level).replace('.', '_')}_atr"] = int(hits[0])+1 if len(hits) else np.nan
        for offset, (date, item) in enumerate(future.iterrows(), 1):
            path = {"event_id": key, "week_offset": offset, "week": date,
                    "rsi_14": item.rsi_14, "rsi_sma_14": item.rsi_sma_14, "spread": item.spread}
            for name in ("open", "high", "low", "close"):
                path[name+"_return"] = item[name]/base-1
                path[name+"_atr"] = (item[name]-base)/atr if atr > 0 else np.nan
            paths.append(path)
        rows.append(row)
    columns = ["event_id", "available_future_weeks"]
    for n in HORIZONS:
        columns += [f"complete_{n}", *[f"{name}_{n}" for name in ("return", "highest_high", "lowest_low", "weeks_to_high", "weeks_to_low", "mfe", "mae", "mfe_atr", "mae_atr")]]
    columns += ["next_opposite_observed", "weeks_until_next_opposite", "return_at_next_opposite", "directional_move_before_opposite", "adverse_move_before_opposite", "path_complete_52"]
    columns += [f"first_hit_{sign}_{str(level).replace('.', '_')}_atr" for level in (.5, 1, 1.5, 2, 3, 4) for sign in ("plus", "minus")]
    path_columns = ["event_id", "week_offset", "week", "rsi_14", "rsi_sma_14", "spread", "open_return", "open_atr", "high_return", "high_atr", "low_return", "low_atr", "close_return", "close_atr"]
    return pd.DataFrame(rows, columns=columns), pd.DataFrame(paths, columns=path_columns)
