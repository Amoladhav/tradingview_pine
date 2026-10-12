"""Legacy formula and composable earnings CLI regression fixtures."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import build_adaptive_range_dataset as adaptive
import directional_range_study as directional
import download_earnings_dates as earnings
import parquet_to_compact_csv as compact


def price_fixture():
    close = np.arange(100.0, 300.0)
    return pd.DataFrame({'Open': close - 0.5, 'High': close + 2,
                         'Low': close - 2, 'Close': close,
                         'Volume': np.full(200, 1000)},
                        index=pd.bdate_range('2023-01-02', periods=200))


class LegacyResearchTests(unittest.TestCase):
    def test_directional_and_adaptive_share_expected_one_day_outcome(self):
        frame = price_fixture()
        # An exaggerated anchor high must not enter forward excursions or ATR.
        frame.iloc[126, frame.columns.get_loc('High')] += 100
        rows = directional.add_forward_excursions(frame, 'SYNTHETIC', 'fixture', [('D', 1)], 21, 'daily bars')
        row = next(row for row in rows if row['anchor_dt'] == frame.index[126])
        anchors, outcomes = adaptive.build_symbol_tables(frame, 'SYNTHETIC', 'fixture')
        outcome = outcomes.loc[(outcomes['anchor_dt'] == frame.index[126]) & (outcomes['x_days'] == 1)].iloc[0]
        anchor = anchors.loc[anchors['anchor_dt'] == frame.index[126]].iloc[0]
        self.assertEqual(row['atr'], 4)
        self.assertEqual(anchor['atr21'], 4)
        self.assertEqual(row['up_excursion_atr'], 0.75)
        self.assertEqual(row['down_excursion_atr'], 0.25)
        self.assertEqual(outcome['up_excursion_atr'], 0.75)
        self.assertEqual(outcome['down_excursion_atr'], 0.25)
        self.assertEqual(outcome['terminal_return_atr'], 0.25)
        self.assertEqual(outcome['end_close'], 227)
        self.assertEqual(len(outcomes), len(anchors) * adaptive.MAX_X)

    def test_future_prices_do_not_change_adaptive_anchor_features(self):
        baseline = price_fixture()
        changed = baseline.copy()
        changed.iloc[151:, :4] *= 10
        first = adaptive.prepare_features(baseline)
        second = adaptive.prepare_features(changed)
        pd.testing.assert_frame_equal(first.iloc[:151], second.iloc[:151])

    def test_earnings_normalization_preserves_source_and_existing_utc_date_rule(self):
        fixture = price_fixture()
        date = fixture.index[126].date().isoformat()
        index = pd.DatetimeIndex([date + ' 16:00', date + ' 18:00'], tz='America/New_York', name='Earnings Date')
        source = pd.DataFrame({'EPS Estimate': ['1.2', 'bad'], 'Reported EPS': [1.3, 1.4], 'Unknown': ['keep', 'source']}, index=index)
        original = source.copy()
        result = earnings.normalize_earnings_frame('SYNTHETIC', source)
        self.assertEqual(len(result), 1)
        self.assertEqual(str(result.iloc[0]['earnings_date']), date)
        self.assertEqual(result.iloc[0]['reported_eps'], 1.4)
        self.assertTrue(pd.isna(result.iloc[0]['eps_estimate']))
        self.assertEqual(str(result['earnings_datetime_utc'].dt.tz), 'UTC')
        pd.testing.assert_frame_equal(source, original)

    def test_earnings_cli_accepts_csv_and_gzip_and_uses_explicit_outputs(self):
        fixture = price_fixture()
        events = pd.DataFrame({'Reported EPS': [1.0]}, index=pd.DatetimeIndex([fixture.index[126]], name='Earnings Date'))
        for suffix in ('.csv', '.csv.gz'):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                input_path = root / ('input' + suffix)
                output = root / 'events.csv'
                coverage = root / 'coverage.csv'
                pd.DataFrame({'symbol': ['SYNTHETIC'], 'anchor_dt': [fixture.index[126]]}).to_csv(input_path, index=False)
                args = ['earnings', '--input', str(input_path), '--output', str(output), '--coverage', str(coverage)]
                class Logger:
                    def message(self, message):
                        pass
                    def progress(self, **kwargs):
                        pass
                with patch('sys.argv', args), patch('research_core.fetching.YahooSource.earnings', return_value=events):
                    earnings.main.__wrapped__(Logger())
                self.assertEqual(pd.read_csv(output)['symbol'].tolist(), ['SYNTHETIC'])
                self.assertEqual(pd.read_csv(coverage)['status'].tolist(), ['ok'])

    def test_legacy_help_creates_no_logs(self):
        for command in (directional, adaptive, earnings, compact):
            with self.subTest(command=command.__name__), patch('sys.argv', [command.__name__, '--help']), patch('research_core.runtime.RunLog', side_effect=AssertionError('no logs')), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as result:
                command.main()
            self.assertEqual(result.exception.code, 0)

    def test_compact_cli_paths_rounding_and_help_no_input_reads(self):
        with patch('sys.argv', ['compact', '--help']), patch('pandas.read_parquet', side_effect=AssertionError('help must not read data')), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as result:
            compact.main()
        self.assertEqual(result.exception.code, 0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            anchor_dir = root / 'anchors'
            outcome_dir = root / 'outcomes'
            anchor_dir.mkdir()
            outcome_dir.mkdir()
            (anchor_dir / 'source.parquet').touch()
            (outcome_dir / 'source.parquet').touch()
            anchor_output = root / 'custom_anchors.csv.gz'
            outcome_output = root / 'custom_outcomes.csv.gz'
            frame = pd.DataFrame({'symbol': ['SYNTHETIC'], 'value': [1.234567891]})
            args = ['compact', '--anchor-dir', str(anchor_dir), '--outcome-dir', str(outcome_dir), '--anchor-output', str(anchor_output), '--outcome-output', str(outcome_output)]
            class Logger:
                def message(self, message):
                    pass
                def progress(self, **kwargs):
                    pass
            with patch('sys.argv', args), patch('pandas.read_parquet', return_value=frame):
                compact.main.__wrapped__(Logger())
            for output in (anchor_output, outcome_output):
                result = pd.read_csv(output)
                self.assertAlmostEqual(result.loc[0, 'value'], 1.234568)
                self.assertEqual(result.loc[0, 'symbol'], 'SYNTHETIC')
