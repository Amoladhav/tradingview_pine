"""Study orchestration and reproducible research artifact export."""
from __future__ import annotations

import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd

from .features import features, weekly_bars
from .outcomes import event_id, outcomes

CONTEXT = ("rsi_14", "rsi_sma_14", "spread", "cross_direction", "return_4", "return_13", "return_26", "price_relative_sma_20", "price_relative_sma_40", "realized_volatility_13")


def build_study(daily_by_symbol: dict[str, pd.DataFrame], as_of: str, sectors=None, progress=None):
    """Quarantine structurally unusable symbols; preserve daily source tables."""
    sectors = sectors or {}
    frames, failures, daily = {}, {}, []
    for symbol, data in daily_by_symbol.items():
        try:
            source = data.copy()
            source.index.name = "date"
            source = source.reset_index()
            source.insert(0, "symbol", symbol)
            daily.append(source)
            weekly = weekly_bars(data, as_of)
            if weekly.empty:
                raise ValueError("no completed weekly bars")
            frames[symbol] = features(weekly)
        except (ValueError, TypeError, KeyError):
            failures[symbol] = "INVALID_DAILY_DATA"
        if progress is not None:
            progress(len(frames) + len(failures), len(daily_by_symbol))
    events, outcome_tables, path_tables, weeks = [], [], [], []
    for symbol, frame in frames.items():
        frame = frame.copy()
        for benchmark in ("SPY", "QQQ", "IWM"):
            context = frames[benchmark].reindex(frame.index) if benchmark in frames else None
            for column in CONTEXT:
                frame[f"market_{benchmark}_{column}"] = context[column] if context is not None else np.nan
            if benchmark == "SPY":
                for n in (4, 13, 26, 52):
                    frame[f"relative_performance_SPY_{n}"] = frame[f"return_{n}"] - context[f"return_{n}"] if context is not None else np.nan
        sector = sectors.get(symbol, "unknown")
        context = frames[sector].reindex(frame.index) if sector in frames and sector != symbol else None
        for n in (4, 13, 26, 52):
            frame[f"relative_performance_sector_{n}"] = frame[f"return_{n}"] - context[f"return_{n}"] if context is not None else np.nan
        selected = frame.loc[frame.cross_direction.ne(0)].copy()
        selected.insert(0, "event_id", [event_id(symbol,d) for d in selected.index])
        selected.insert(0, "symbol", symbol)
        selected.insert(2, "sector_etf", sector)
        selected.index.name = "week"
        events.append(selected.reset_index())
        result, paths = outcomes(frame, symbol)
        outcome_tables.append(result)
        path_tables.append(paths)
        frame.insert(0, "symbol", symbol)
        frame.index.name = "week"
        weeks.append(frame.reset_index())
    def combine(tables):
        return pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
    tables = {"rsi_weekly_bars": combine(weeks), "rsi_cross_events": combine(events),
              "rsi_cross_outcomes": combine(outcome_tables), "rsi_cross_paths": combine(path_tables),
              "rsi_daily_bars": combine(daily)}
    metadata = {"schema_version": 1, "as_of_exclusive": as_of,
                "requested_universe": list(daily_by_symbol), "successful_symbols": list(frames),
                "failures": failures, "sectors": sectors,
                "source": "caller supplied daily tables; original provider capture retained separately",
                "price_basis": "raw OHLC, provider adjusted close retained separately",
                "weekly_rule": "W-FRI; include only Friday labels earlier than as_of; US exchange-local daily dates",
                "rsi": "Wilder RMA14 seeded with SMA of first 14 valid changes; down=0 wins flat tie",
                "warnings": ["Exploratory present-day universe has survivorship bias.",
                             "Raw OHLC features are not dividend adjusted; verify provider split methodology.",
                             "No exchange calendar validation; missing sessions are not imputed.",
                             "Reliable historical earnings unavailable: earnings output omitted.",
                             "TradingView parity, live source acceptance and platform acceptance pending.",
                             "Paths near end of sample are censored; complete_N flags distinguish outcomes."],
                "versions": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__}}
    missing_benchmarks = [symbol for symbol in ("SPY", "QQQ", "IWM") if symbol not in frames]
    metadata["missing_market_benchmarks"] = missing_benchmarks
    if missing_benchmarks:
        metadata["warnings"].append("Market benchmark coverage incomplete; unavailable context columns remain NA.")
    return tables, metadata


def definition(column):
    """Machine-readable naming grammar paired with the full formula specification."""
    exact = {
        "event_id": ("symbol:Friday:rsi14-sma14-v1", "identifier"),
        "symbol": ("provider symbol", "identifier"), "week": ("Friday period label", "date"),
        "Open": ("provider daily open, preserved unchanged", "price"),
        "High": ("provider daily high, preserved unchanged", "price"),
        "Low": ("provider daily low, preserved unchanged", "price"),
        "Close": ("provider daily close, preserved unchanged", "price"),
        "Adj Close": ("provider daily adjusted close, preserved unchanged; adjustment semantics require source verification", "price"),
        "Volume": ("provider daily volume, preserved unchanged", "shares"),
        "Dividends": ("provider daily cash dividend amount, preserved unchanged", "provider currency/share"),
        "Stock Splits": ("provider split ratio, preserved unchanged", "ratio"),
        "date": ("source daily observation date", "date"),
        "cross_direction": ("1: spread>0 and prior<=0; -1: spread<0 and prior>=0; otherwise 0", "signed category"),
        "rsi_14": ("100-100/(1+RMA14(up)/RMA14(down)); zero rules in specification", "RSI points"),
        "spread": ("RSI14-SMA14(RSI14)", "RSI points"),
        "true_range": ("max(high-low,abs(high-prior_close),abs(low-prior_close))", "price"),
        "directional_efficiency": ("abs(close-open)/(high-low)", "ratio"),
        "close_location": ("(close-low)/(high-low)", "ratio"),
        "body": ("close-open", "price"), "gap": ("open-prior_close", "price"),
        "volume_robust_zscore_26": ("(volume-median26)/(1.4826*median26(abs(volume-median26)))", "robust z score"),
    }
    if column in exact:
        return exact[column]
    # Every generated column retains an explicit formula family plus parameters.
    name = column.replace("_", " ")
    if column.startswith("market_"):
        _, benchmark, nested = column.split("_", 2)
        formula, units = definition(nested)
        return (f"Same Friday {benchmark}: {formula}; missing benchmark remains NA", units)
    if column.startswith("relative_performance_"):
        return ("symbol close/close_N_weeks_ago-1 minus benchmark close/close_N_weeks_ago-1; N=final suffix", "return fraction")
    if column.startswith("rsi_sma_") and column[8:].isdigit():
        return ("SMA of RSI14 over N observations; N=final suffix; full warmup required", "RSI points")
    if "percentile" in column:
        return (f"{name}: trailing empirical fraction of values <= current; window suffix", "fraction, not probability")
    if "ols_slope" in column:
        return (f"{name}: sum((i-mean(i))*value_i)/sum((i-mean(i))^2); N observations; change=first difference; normalized=/close; strengthening=abs(slope)>abs(prior slope)", "points or price/week; normalized fraction/week")
    if "endpoint_slope" in column:
        return (f"{name}: (current-value N-1 weeks ago)/(N-1); change=first difference; normalized=/close; strengthening=absolute comparison", "points or price/week")
    if column.startswith("rsi_zone_"):
        return ("lower <= RSI14 <= upper; bounds in suffix; flags overlap at boundaries", "boolean")
    if column in ("rsi_below_20", "rsi_above_80"):
        return ("RSI14 < 20" if column.endswith("20") else "RSI14 > 80", "boolean")
    if column.startswith("rsi_distance_"):
        return ("RSI14 minus reference level in suffix", "RSI points")
    if column.startswith("cross_velocity_"):
        return ("(OLS_N(RSI14)-OLS_N(SMA14(RSI14)))/100", "normalized RSI range/week")
    if column.startswith("crosses_prior_"):
        return ("sum(cross_direction!=0) in N weeks strictly before current week", "count")
    if column.startswith("weeks_since_rsi_"):
        return ("distance in weeks to most recent trailing extremum, including current; N=final suffix", "weeks")
    if column == "sma_slope_sign_changed":
        return ("sign(SMA14.diff()) differs from prior sign; both slopes available; zero is a sign", "boolean")
    if column == "weeks_since_sma_slope_sign_change":
        return ("current positional week minus latest observed SMA first-difference sign-change week", "weeks")
    if column == "weeks_since_previous_cross":
        return ("current week minus most recent strictly prior crossing week", "weeks")
    if column == "weeks_on_previous_side":
        return ("length of immediately preceding consecutive equal-sign nonzero spread run", "weeks")
    if column == "max_absolute_spread_since_previous_cross":
        return ("max(abs(spread)) from previous cross inclusive to week before event inclusive", "RSI points")
    if column == "absolute_spread":
        return ("abs(RSI14-SMA14(RSI14))", "RSI points")
    if column == "spread_slope":
        return ("spread minus prior spread", "RSI points/week")
    if "pivot" in column:
        return ("strict centered three-bar extremum confirmed one week later; latest and previous confirmed values carried forward; change=latest-previous; higher/lower=sign(change)", "price or RSI points; flags boolean")
    if "_previous_" in column:
        return ("named measurement shifted N completed weeks; N=final suffix", "same units as measurement")
    if column.startswith(("rsi_change_", "rsi_sma_change_", "price_change_")) and column.rsplit("_",1)[-1].isdigit():
        return ("named series current minus value N weeks ago", "RSI points or price")
    if any(token in column for token in ("_minimum_", "_maximum_", "_range_")) and column.rsplit("_",1)[-1].isdigit():
        return ("trailing minimum, maximum or max-min of named series over N observations, current included", "RSI points or price")
    if column.startswith("distance_high_") or column.startswith("distance_low_"):
        return ("close / trailing maximum high (or minimum low) over N weeks - 1", "fraction")
    if column.startswith("price_high_change_") or column.startswith("price_low_change_"):
        return ("first difference of trailing N-week maximum high or minimum low", "price")
    if column.startswith("price_sma_slope_change_"):
        return ("second difference of SMA_N(close)", "price/week squared")
    if column.startswith("price_sma_slope_"):
        return ("first difference of SMA_N(close)", "price/week")
    if column.startswith("price_relative_sma_"):
        return ("close/SMA_N(close)-1", "fraction")
    if column.startswith("price_sma_"):
        return ("arithmetic mean of N weekly closes", "price")
    if column.startswith("atr_percent_"):
        return ("100 * RMA_N(true_range)/close", "percent")
    if column.startswith("atr_expansion_"):
        return ("ATR_N/current mean of N strictly prior ATR_N values", "ratio")
    if column.startswith("atr_"):
        return ("Wilder RMA_N(true_range), SMA seeded", "price")
    if column.startswith("realized_volatility_ratio_"):
        return ("current annualized N-week sample return stdev / prior week's same statistic", "ratio")
    if column.startswith("realized_volatility_"):
        return ("sample stdev(weekly close/previous_close-1,N)*sqrt(52)", "annualized return fraction")
    if column.startswith("volume_average_"):
        return ("arithmetic mean of N weekly volumes, current included", "shares")
    if column.startswith("relative_volume_"):
        return ("weekly volume / SMA_N(weekly volume); previous_K shifts by K weeks", "ratio")
    if column.endswith("_atr_per_relative_volume"):
        return ("named price measurement / ATR14 / relative_volume13", "ratio")
    if column.endswith("_per_volume"):
        return ("named price change, absolute change or true range divided by weekly volume", "price/share")
    if column.endswith("_fraction_range"):
        return ("named body or wick / (high-low)", "ratio")
    if column == "body_atr_times_relative_volume":
        return ("(close-open)/ATR14 * (volume/SMA13(volume))", "ratio")
    if column in ("body_atr", "range_atr", "return_atr"):
        return ({"body_atr":"(close-open)/ATR14", "range_atr":"(high-low)/ATR14", "return_atr":"(close-prior_close)/ATR14"}[column], "ATR units")
    candle = {"absolute_body":"abs(close-open)", "candle_range":"high-low", "upper_wick":"high-max(open,close)", "lower_wick":"min(open,close)-low"}
    if column in candle:
        return (candle[column], "price")
    if column in ("weekly_return",) or column.startswith("return_") and column[7:].isdigit():
        return ("predictors: close/close_N_weeks_ago-1; outcomes: close_N_weeks_after_event/event_close-1; weekly_return N=1", "return fraction")
    if column.startswith("daily_"):
        daily_definitions = {"daily_up_days":"count daily close/previous_daily_close-1 > 0", "daily_down_days":"count daily return < 0", "daily_realized_volatility":"sample stdev of daily close returns in event week, not annualized", "daily_largest_up_return":"maximum strictly positive daily return in week; NA if none", "daily_largest_down_return":"minimum strictly negative daily return in week; NA if none", "daily_high_weekday":"weekday of first maximum high; Monday=0", "daily_low_weekday":"weekday of first minimum low; Monday=0"}
        return (daily_definitions.get(column,"volume on Nth observed trading date of week; N=suffix; missing dates remain NA"), "count, weekday, return fraction, or shares as named")
    if column.startswith("complete_") or column == "path_complete_52":
        return ("all N subsequent weekly observations available; N=final suffix", "boolean")
    if column.startswith(("mfe_", "mae_")):
        return ("MFE=max(0,directional favorable excursion); MAE=min(0,directional adverse excursion); subsequent weeks 1..N; bull up favorable, bear down favorable; /event close or /event ATR14 for _atr_", "return fraction or ATR units")
    if column.startswith(("highest_high_", "lowest_low_")):
        return ("maximum high or minimum low strictly after event over weeks 1..N; NA unless full horizon", "price")
    if column.startswith(("weeks_to_high_", "weeks_to_low_")):
        return ("offset to first maximum high or minimum low within subsequent weeks 1..N", "weeks")
    if column.startswith("first_hit_"):
        return ("first subsequent weekly high >= event close+K*event ATR14 (plus), or low <= close-K*ATR14 (minus); K in name; bounded 52 weeks; NA=no observed hit, inspect path_complete_52", "weeks")
    if column in ("next_opposite_observed",):
        return ("an opposite cross occurs later in available history", "boolean")
    if column == "weeks_until_next_opposite":
        return ("next opposite cross week minus event week; NA if censored", "weeks")
    if column == "return_at_next_opposite":
        return ("close at next opposite cross / event close - 1; NA if censored", "return fraction")
    if column in ("directional_move_before_opposite", "adverse_move_before_opposite"):
        return ("directional MFE or signed MAE over following bars through opposite-cross bar inclusive / event close; NA if opposite cross censored", "return fraction")
    if column in ("available_future_weeks", "week_offset"):
        return ("number of weekly observations after event, or current path offset beginning at 1", "weeks")
    if column in ("open_return","high_return","low_return","close_return"):
        return ("future named OHLC / event close - 1", "return fraction")
    if column in ("open_atr","high_atr","low_atr","close_atr"):
        return ("(future named OHLC - event close) / event ATR14", "ATR units")
    if column in ("open", "high", "low", "close", "adjusted_close"):
        return ("weekly first open, max high, min low, final close or final provider adjusted close from observed daily bars", "price")
    if column == "volume":
        return ("sum of observed daily volumes in week", "shares")
    if column == "trading_days":
        return ("number of observed daily rows in week; not exchange-calendar validated", "count")
    if column == "observed_week":
        return ("trading_days > 0", "boolean")
    if column == "sector_etf":
        return ("explicit study sector comparator mapping; unknown if unmapped", "symbol")
    return ("unaltered source column retained from decoded provider DataFrame; interpretation intentionally not inferred for unknown fields", "provider-defined; unverified")


def write_study(tables, metadata, output_dir):
    """Write only study outputs to a new run directory; caller packages exact files."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    written, dictionary = [], []
    for name, frame in tables.items():
        path = output / (name + ".csv.gz")
        frame.to_csv(path, index=False, compression={"method": "gzip", "mtime": 0})
        written.append(path)
        kind = "future/outcome" if name in ("rsi_cross_outcomes", "rsi_cross_paths") else "predictor/source"
        for column in frame:
            formula, units = definition(column)
            dictionary.append({"table": name, "column": column, "definition": column.replace("_", " "),
                               "formula": formula, "units": units, "role": kind})
    path = output / "rsi_data_dictionary.csv"
    pd.DataFrame(dictionary).to_csv(path, index=False)
    written.append(path)
    events = tables["rsi_cross_events"]
    weekly = tables["rsi_weekly_bars"]
    summary = {"successful_symbols": len(metadata["successful_symbols"]),
               "failed_symbols": metadata["failures"], "weekly_observations": len(weekly),
               "bull_crosses": int(events.cross_direction.eq(1).sum()) if len(events) else 0,
               "bear_crosses": int(events.cross_direction.eq(-1).sum()) if len(events) else 0,
               "coverage_start": str(weekly.week.min()) if len(weekly) else None,
               "coverage_end": str(weekly.week.max()) if len(weekly) else None,
               "events_by_year": events.week.dt.year.value_counts().sort_index().to_dict() if len(events) else {},
               "events_by_decade": ((events.week.dt.year//10)*10).value_counts().sort_index().to_dict() if len(events) else {},
               "events_by_sector": events.sector_etf.value_counts().to_dict() if len(events) else {},
               "missing_values": {name: int(frame.isna().sum().sum()) for name,frame in tables.items()},
               "validation": {"event_ids_unique": bool(events.event_id.is_unique) if len(events) else True,
                              "future_columns_separate": True, "live_manual_validation": "pending"}}
    metadata["summary"] = summary
    for filename, value in (("rsi_study_metadata.json",metadata),("rsi_study_summary.txt",summary)):
        path = output / filename
        path.write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")
        written.append(path)
    return written
