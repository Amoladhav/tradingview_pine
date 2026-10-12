"""Deterministic numerical tests; runner denies network and credential access."""
import tempfile
import contextlib
import io
import json
import tarfile
from unittest.mock import patch
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from rsi_research.features import features, rma, rsi, weekly_bars
from rsi_research.pipeline import build_study, write_study
from rsi_research.outcomes import outcomes


def daily_fixture(periods=1600):
    index = pd.bdate_range("2010-01-04", periods=periods)
    close = 100 + np.arange(periods)*.01 + 12*np.sin(np.arange(periods)/25)
    return pd.DataFrame({"Open": close-.2, "High":close+1, "Low":close-1,
                         "Close":close, "Adj Close":close*.9, "Volume":1000+np.arange(periods)%100}, index=index)


class ResearchTests(unittest.TestCase):
    def test_wilder_seed_and_recursive_update(self):
        values = pd.Series([1.,2.,3.,4.,5.])
        result = rma(values, 3)
        self.assertTrue(result.iloc[:2].isna().all())
        self.assertAlmostEqual(result.iloc[2], 2)
        self.assertAlmostEqual(result.iloc[3], 8/3)
        self.assertAlmostEqual(result.iloc[4], 31/9)
        self.assertEqual(rsi(pd.Series(range(30), dtype=float)).iloc[-1],100)
        self.assertEqual(rsi(pd.Series(range(30,0,-1), dtype=float)).iloc[-1],0)
        self.assertEqual(rsi(pd.Series([1.]*30)).iloc[-1],100)

    def test_completed_week_cutoff_and_aggregation(self):
        data = daily_fixture(10)
        first = weekly_bars(data,"2010-01-08")
        self.assertEqual(len(first),0)
        full = weekly_bars(data,"2010-01-09")
        self.assertEqual(len(full),1)
        self.assertEqual(full.trading_days.iloc[0],5)
        self.assertAlmostEqual(full.open.iloc[0],data.Open.iloc[0])
        self.assertAlmostEqual(full.close.iloc[0],data.Close.iloc[4])
        self.assertAlmostEqual(full.volume.iloc[0],data.Volume.iloc[:5].sum())

    def test_predictors_causal_under_future_mutation(self):
        weekly = weekly_bars(daily_fixture(),"2020-01-01")
        original = features(weekly)
        changed = weekly.copy()
        changed.loc[changed.index[180]:,["open","high","low","close"]] *= 2
        altered = features(changed)
        pd.testing.assert_frame_equal(original.iloc[:180],altered.iloc[:180])
        short = features(weekly.iloc[:180])
        pd.testing.assert_frame_equal(original.iloc[:180],short)

    def test_forward_outcomes_use_following_bars_and_censor(self):
        idx = pd.date_range("2020-01-03",periods=4,freq="W-FRI")
        frame = pd.DataFrame({"open":[100,101,102,103],"close":[100,110,90,105],
            "high":[999,115,120,110],"low":[1,95,80,100],"atr_14":[10]*4,
            "rsi_14":[50]*4,"rsi_sma_14":[49]*4,"spread":[1]*4,"cross_direction":[1,0,-1,0]},index=idx)
        result,paths=outcomes(frame,"TEST")
        event=result.iloc[0]
        self.assertAlmostEqual(event.return_1,.1)
        self.assertAlmostEqual(event.mfe_2,.2)
        self.assertAlmostEqual(event.mae_2,-.2)
        self.assertEqual(event.weeks_to_high_2,2)
        self.assertEqual(event.weeks_until_next_opposite,2)
        self.assertFalse(event.complete_4)
        self.assertTrue(np.isnan(event.return_4))
        self.assertAlmostEqual(result.iloc[1].mfe_1,0)
        self.assertEqual(paths.week_offset.min(),1)

    def test_pipeline_tables_dictionary_and_archive_inputs(self):
        tables,meta=build_study({"TEST":daily_fixture(),"SPY":daily_fixture()},"2020-01-01")
        self.assertGreater(len(tables["rsi_cross_events"]),0)
        self.assertEqual(meta["failures"],{})
        self.assertNotIn("return_39",tables["rsi_cross_events"])
        self.assertIn("market_SPY_rsi_14",tables["rsi_cross_events"])
        self.assertTrue(tables["rsi_cross_events"].market_QQQ_rsi_14.isna().all())
        self.assertIn("QQQ", meta["missing_market_benchmarks"])
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/"run"
            files=write_study(tables,meta,output)
            self.assertEqual(len(files),8)
            dictionary=pd.read_csv(output/"rsi_data_dictionary.csv")
            self.assertEqual(len(dictionary),sum(len(t.columns) for t in tables.values()))
            self.assertFalse(dictionary.formula.isna().any())
            derived = dictionary.loc[dictionary.table.ne("rsi_daily_bars")]
            self.assertFalse(derived.formula.str.startswith("unaltered source").any())
            with self.assertRaises(FileExistsError):
                write_study(tables,meta,output)

    def test_empty_event_tables_keep_full_headers(self):
        data = daily_fixture(300)
        data["Close"] = 100.
        data["Open"] = 100.
        data["High"] = 101.
        data["Low"] = 99.
        tables, metadata = build_study({"FLAT": data}, "2020-01-01")
        self.assertEqual(len(tables["rsi_cross_events"]), 0)
        self.assertIn("return_52", tables["rsi_cross_outcomes"])
        self.assertIn("close_atr", tables["rsi_cross_paths"])
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/"empty"
            write_study(tables, metadata, output)
            self.assertEqual(len(pd.read_csv(output/"rsi_cross_outcomes.csv.gz")), 0)

    def test_timezone_holiday_and_adjusted_missingness(self):
        data = daily_fixture(5).drop(pd.Timestamp("2010-01-06"))
        data.index = data.index.tz_localize("America/New_York")
        data.iloc[-1, data.columns.get_loc("Adj Close")] = np.nan
        weekly = weekly_bars(data, "2010-01-09")
        self.assertEqual(weekly.trading_days.iloc[0], 4)
        self.assertTrue(np.isnan(weekly.adjusted_close.iloc[0]))
        self.assertTrue(np.isnan(weekly.daily_largest_down_return.iloc[0]))
        bad = data.copy()
        bad.index = pd.date_range("2010-01-09", periods=len(bad))
        with self.assertRaises(ValueError):
            weekly_bars(bad, "2010-01-20")

    def test_bear_horizon_and_repeated_same_direction(self):
        frame = features(weekly_bars(daily_fixture(400), "2020-01-01"))
        frame["cross_direction"] = 0
        frame.iloc[0, frame.columns.get_loc("cross_direction")] = -1
        frame.iloc[2, frame.columns.get_loc("cross_direction")] = -1
        frame.iloc[4, frame.columns.get_loc("cross_direction")] = 1
        frame["atr_14"] = 10.
        result, _ = outcomes(frame, "TEST")
        self.assertEqual(result.weeks_until_next_opposite.iloc[0], 4)
        base = frame.close.iloc[0]
        self.assertAlmostEqual(result.mfe_52.iloc[0], max(0, base-frame.low.iloc[1:53].min())/base)
        self.assertAlmostEqual(result.mae_52.iloc[0], min(0, base-frame.high.iloc[1:53].max())/base)

    def test_cli_rejects_non_date_cutoffs(self):
        import rsi_weekly_study
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            for value in ("NaT", "2020-01-01T00:00:00Z", "2020-1-1", "2020-02-31"):
                self.assertEqual(rsi_weekly_study.main(["--as-of", value, "--output-dir", str(Path(tmp)/"run")]), 1)

    def test_cli_archive_and_failed_packaging_status(self):
        import rsi_weekly_study
        class Source:
            def history(self, *args, **kwargs):
                return daily_fixture(500)
        with tempfile.TemporaryDirectory() as tmp, patch.object(rsi_weekly_study, "source_from_args", return_value=Source()):
            output = Path(tmp)/"run"
            with contextlib.redirect_stdout(io.StringIO()) as console:
                status = rsi_weekly_study.main(["--symbols", "test", "--as-of", "2020-01-01", "--output-dir", str(output)])
            self.assertEqual(status, 0, console.getvalue())
            self.assertIn("STUDY COMPLETE", console.getvalue())
            with tarfile.open(output/"rsi_sma_weekly_study.tar.gz") as archive:
                names = archive.getnames()
                self.assertIn("source/rsi_weekly_study.py", names)
                self.assertIn("source/docs/RSI_STUDY.md", names)
                self.assertFalse(any("cache" in name or "venv" in name for name in names))
            failed_output = Path(tmp)/"failed"
            with patch.object(rsi_weekly_study.tarfile, "open", side_effect=OSError("synthetic")), contextlib.redirect_stdout(io.StringIO()) as console:
                status = rsi_weekly_study.main(["--symbols", "TEST", "--as-of", "2020-01-01", "--output-dir", str(failed_output)])
            self.assertEqual(status, 1)
            self.assertNotIn("STUDY COMPLETE", console.getvalue())
            reports = [json.loads(p.read_text()) for p in (Path(tmp)/"agent-review").glob("*.json")]
            self.assertIn("failed", [r["stage"] for r in reports])

    def test_invalid_symbol_does_not_abort_study(self):
        data=daily_fixture()
        bad=data.copy()
        bad.iloc[5,bad.columns.get_loc("Volume")]=-1
        tables,meta=build_study({"GOOD":data,"BAD":bad},"2020-01-01")
        self.assertEqual(meta["successful_symbols"],["GOOD"])
        self.assertIn("BAD",meta["failures"])
        self.assertEqual(len(tables["rsi_daily_bars"]),2*len(data))


if __name__ == "__main__":
    unittest.main()
