"""Synthetic collector regressions; use the repository's isolated test runner."""
import importlib.util
from pathlib import Path
import unittest
import contextlib
import io
import tempfile
from unittest.mock import patch

import numpy as np
import pandas as pd


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


daily = load_module('daily_collector', 'range_collector/collect.py')
intraday = load_module('intraday_collector', 'intraday_collector/collect_intraday.py')


class CollectorTests(unittest.TestCase):
    def daily_fixture(self):
        close = 100 + np.arange(300) * .1 + np.sin(np.arange(300) / 7)
        return pd.DataFrame({'Open': close - .3, 'High': close + 1,
                             'Low': close - 1, 'Close': close,
                             'Volume': np.full(300, 10000)},
                            index=pd.bdate_range('2020-01-01', periods=300))

    def test_daily_labels_use_complete_future_sessions(self):
        data = self.daily_fixture()
        anchors, outcomes = daily.calculate_features(data, 'SYN', 'Synthetic', 3)
        first = anchors.iloc[0]
        at = data.index.get_loc(pd.Timestamp(first.anchor_dt))
        horizon = outcomes[(outcomes.anchor_dt == first.anchor_dt) & (outcomes.x_days == 3)].iloc[0]
        expected = data.Close.iloc[at + 3]
        self.assertAlmostEqual(horizon.end_close, expected)
        self.assertAlmostEqual(horizon.terminal_return_atr,
                               (expected - first.anchor_close) / first.atr21)
        self.assertAlmostEqual(horizon.up_excursion_atr,
                               max((data.High.iloc[at + 1:at + 4].max() - first.anchor_close) / first.atr21, 0))
        latest = data.index[-1].strftime('%Y-%m-%d')
        self.assertNotIn(latest, outcomes.anchor_dt.tolist())
        self.assertEqual(len(outcomes[outcomes.x_days == 1]), len(anchors) - 1)
        self.assertEqual(len(outcomes[outcomes.x_days == 3]), len(anchors) - 3)

    def test_future_prices_do_not_change_earlier_features(self):
        data = self.daily_fixture()
        before, _ = daily.calculate_features(data, 'SYN', 'Synthetic', 2)
        changed = data.copy()
        changed.iloc[-20:, :4] *= 2
        after, _ = daily.calculate_features(changed, 'SYN', 'Synthetic', 2)
        cutoff = data.index[-20].strftime('%Y-%m-%d')
        pd.testing.assert_frame_equal(before[before.anchor_dt < cutoff], after[after.anchor_dt < cutoff])

    def test_daily_rejects_invalid_horizon_and_short_input(self):
        with self.assertRaises(ValueError):
            daily.calculate_features(self.daily_fixture(), 'SYN', 'Synthetic', 0)
        with self.assertRaises(ValueError):
            daily.calculate_features(self.daily_fixture().iloc[:100], 'SYN', 'Synthetic', 2)

    def test_intraday_regular_session_timezone_and_duplicates(self):
        index = pd.to_datetime(['2024-03-08T14:00Z', '2024-03-08T14:30Z',
                                '2024-03-11T13:30Z', '2024-03-11T13:30Z',
                                '2024-03-11T20:00Z', '2024-03-09T14:30Z'])
        frame = pd.DataFrame({'Open': 10, 'High': 11, 'Low': 9, 'Close': 10.5, 'Volume': 20}, index=index)
        result = intraday.normalize(frame, 'SYN', '30m')
        self.assertEqual(len(result), 2)
        self.assertTrue(result.timestamp_et.iloc[0].endswith('-0500'))
        self.assertTrue(result.timestamp_et.iloc[1].endswith('-0400'))
        self.assertTrue(all('T09:30' in item for item in result.timestamp_et))
        with self.assertRaises(ValueError):
            intraday.normalize(frame.tz_localize(None), 'SYN', '30m')

    def test_intraday_audit_invalid_rows(self):
        frame = pd.DataFrame({'open': [10, 10, 10], 'high': [11, 9, 11],
                              'low': [9, 9, 9], 'close': [10, 10, 10],
                              'volume': [20, 20, -1], 'session_date': ['2024-01-02'] * 3})
        clean, stats = intraday.audit(frame, '30m')
        self.assertEqual(len(clean), 1)
        self.assertEqual(stats['invalid_rows_dropped'], 2)
        self.assertEqual(stats['sessions_with_fewer_than_expected_bars'], 1)

    def test_collect_preserves_provider_parameters(self):
        class Source:
            mode = 'cache'
            def history(self, symbol, **kwargs):
                self.kwargs = kwargs
                return pd.DataFrame({'x': [1]})
        source = Source()
        intraday.collect('SYN', '30m', '59d', 0, source)
        self.assertEqual(source.kwargs, {'period': '59d', 'interval': '30m',
                         'prepost': False, 'auto_adjust': False, 'actions': False, 'method': 'history'})

    def test_daily_cli_only_bypasses_universe_and_reports_partial_failure(self):
        data = self.daily_fixture()
        class Source:
            def history(self, symbol, **kwargs):
                if symbol == 'FAIL':
                    raise RuntimeError('private exception text must not escape')
                return data
        with tempfile.TemporaryDirectory() as directory:
            stream = io.StringIO()
            with patch.object(daily, 'source_from_args', return_value=Source()), \
                 patch.object(daily, 'select', side_effect=AssertionError('unexpected selection')), \
                 contextlib.redirect_stdout(stream):
                result = daily.main(['--only', 'SYN,FAIL', '--stocks-file', 'does-not-exist.csv',
                                     '--out', directory, '--max-x', '2'])
            self.assertEqual(result, 1)
            self.assertTrue((Path(directory) / 'SYN_anchors.csv.gz').exists())
            manifest = pd.read_csv(Path(directory) / 'manifest.csv')
            self.assertEqual(manifest.status.tolist(), ['ok', 'error'])
            self.assertNotIn('private exception text', stream.getvalue())
            self.assertNotIn('private exception text', manifest.to_csv())

    def test_stock_selection_requires_explicit_fetch(self):
        with patch.object(daily, 'select') as select, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as failure:
                daily.main(['--select-stocks'])
            self.assertEqual(failure.exception.code, 2)
            select.assert_not_called()

    def test_invalid_cli_inputs_never_construct_source(self):
        cases = (
            (daily, ['--only', '../bad']),
            (daily, ['--only', '']),
            (daily, ['--start', 'NaT']),
            (daily, ['--start', '2024-02-02', '--end', '2024-01-01']),
            (intraday, ['--only', '../bad']),
            (intraday, ['--period', ' ']),
        )
        for module, arguments in cases:
            with self.subTest(arguments=arguments), \
                 patch.object(module, 'source_from_args') as source, \
                 contextlib.redirect_stdout(io.StringIO()) as stream:
                self.assertEqual(module.main(arguments), 1)
                source.assert_not_called()
                self.assertNotIn('Traceback', stream.getvalue())

    def test_parser_validation_never_constructs_source_or_reads_credentials(self):
        for module, arguments in (
            (daily, ['--refresh']), (intraday, ['--refresh']),
            (daily, ['--select-stocks']),
            (daily, ['--select-stocks', '--fetch', '--only', '']),
            (intraday, ['--pause', 'nan']), (intraday, ['--pause', 'inf']),
            (intraday, ['--retries', '-1']),
        ):
            with self.subTest(arguments=arguments), \
                 patch.object(module, 'source_from_args') as source, \
                 patch.object(daily.os, 'getenv') as credential_lookup, \
                 contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as failure:
                    module.main(arguments)
                self.assertEqual(failure.exception.code, 2)
                source.assert_not_called()
                credential_lookup.assert_not_called()

    def test_cli_source_failure_and_cancellation_are_sanitized(self):
        for module in (daily, intraday):
            for error, expected in ((OSError('private failure details'), 1),
                                    (KeyboardInterrupt(), 130)):
                with self.subTest(module=module.__name__, error=type(error).__name__), \
                     patch.object(module, 'source_from_args', side_effect=error), \
                     contextlib.redirect_stdout(io.StringIO()) as stream:
                    self.assertEqual(module.main(['--only', 'SYN']), expected)
                    self.assertNotIn('private failure details', stream.getvalue())
                    self.assertNotIn('Traceback', stream.getvalue())

    def test_default_cache_failure_never_resolves_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            for module in (daily, intraday):
                with self.subTest(module=module.__name__), \
                     patch.object(daily.os, 'getenv') as credential_lookup, \
                     contextlib.redirect_stdout(io.StringIO()) as stream:
                    result = module.main(['--only', 'SYN', '--cache-dir', directory,
                                          '--out', str(Path(directory) / module.__name__)])
                    self.assertEqual(result, 1)
                    credential_lookup.assert_not_called()
                    self.assertIn('failed: attempted=1 succeeded=0 failed=1', stream.getvalue())
                    self.assertNotIn('completed:', stream.getvalue())
