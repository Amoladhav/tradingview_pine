"""Synthetic tests only; the runner installs network denial before imports."""
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import pandas as pd
from research_core.capture import CaptureStore
from research_core.errors import ResearchError, safe_error_code
from research_core.fetching import YahooSource
from research_core.io import atomic_csv, validate_symbol
from research_core.runtime import RunLog


class CoreTests(unittest.TestCase):
    def test_decoded_capture_preserves_unknown_columns_missing_values_and_timezone(self):
        index = pd.date_range('2024-03-08', periods=5, tz='America/New_York', name='Date')
        frame = pd.DataFrame({'Close': [1.0, 2, float('nan'), 4, 5], 'Unknown': ['a', None, '', 'x', 'y']}, index=index)
        frame.columns = pd.MultiIndex.from_tuples([('Close', 'FAKE'), ('Unknown', 'FAKE')], names=['Price', 'Ticker'])
        with tempfile.TemporaryDirectory() as directory:
            store = CaptureStore(directory)
            first = store.save({'kind': 'synthetic'}, frame)
            second = store.save({'kind': 'synthetic'}, frame)
            self.assertNotEqual(first, second)
            pd.testing.assert_frame_equal(store.load({'kind': 'synthetic'}), frame, check_freq=False)

    def test_cache_mode_never_imports_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            source = YahooSource(directory)
            with self.assertRaisesRegex(ResearchError, 'CACHE_MISS'):
                source.history('FAKE')

    def test_fetch_captures_before_projection_and_replays(self):
        frame = pd.DataFrame({'Close': [4.0], 'Future Field': ['unusual']}, index=pd.to_datetime(['2024-01-01']))
        fake = types.SimpleNamespace(download=lambda *a, **kw: frame, __version__='synthetic')
        with tempfile.TemporaryDirectory() as directory, patch.dict('sys.modules', {'yfinance': fake}):
            source = YahooSource(directory, mode='fetch', pause=0)
            actual = source.history('FAKE', auto_adjust=False)
            actual = actual[['Close']]
            replay = YahooSource(directory).history('FAKE', auto_adjust=False)
            self.assertIn('Future Field', replay)
            pd.testing.assert_frame_equal(frame, replay)

    def test_provider_failure_does_not_leak_text(self):
        def fail(*args, **kwargs):
            raise ValueError('private-provider-error')
        fake = types.SimpleNamespace(download=fail)
        with tempfile.TemporaryDirectory() as directory, patch.dict('sys.modules', {'yfinance': fake}):
            with self.assertRaisesRegex(ResearchError, '^PUBLIC_FETCH_FAILED$'):
                YahooSource(directory, mode='fetch', pause=0).history('FAKE')
            self.assertEqual(list(Path(directory).rglob('*.json')), [])

    def test_invalid_capture_and_unsafe_symbols_fail_closed(self):
        with self.assertRaisesRegex(ResearchError, 'INVALID_SYMBOL'):
            validate_symbol('../escape')
        with tempfile.TemporaryDirectory() as directory:
            store = CaptureStore(directory)
            path = store.save({'kind': 'synthetic'}, pd.DataFrame({'x': [1]}))
            path.write_text('invalid', encoding='utf-8')
            with self.assertRaisesRegex(ResearchError, 'CAPTURE_INVALID'):
                store.load({'kind': 'synthetic'})

    def test_atomic_csv_keeps_previous_output_when_write_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'output.csv'
            path.write_text('previous', encoding='utf-8')
            fake = types.SimpleNamespace(to_csv=lambda *a, **kw: (_ for _ in ()).throw(ValueError('bad data')))
            with self.assertRaises(ValueError):
                atomic_csv(fake, path)
            self.assertEqual(path.read_text(), 'previous')
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_logs_plain_redirected_output_and_sanitized_partial_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with RunLog('synthetic', directory, total=2, stream=output) as log:
                log.progress(success=True)
                log.error(ValueError('private-error'))
                log.progress(success=False)
            self.assertNotIn('\x1b', output.getvalue())
            self.assertNotIn('private-error', output.getvalue())
            report = json.loads(log.report_path.read_text())
            self.assertEqual(report['stage'], 'partial')
            self.assertEqual(report['counts'], {'attempted': 2, 'succeeded': 1, 'failed': 1})
            self.assertNotIn('private-error', log.errors_path.read_text())

    def test_cancelled_runs_do_not_claim_success(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(KeyboardInterrupt):
                with RunLog('synthetic', directory, stream=io.StringIO()) as log:
                    raise KeyboardInterrupt()
            self.assertEqual(json.loads(log.report_path.read_text())['stage'], 'cancelled')

    def test_fetch_reuses_cache_unless_refresh_is_explicit(self):
        calls = []
        def download(*args, **kwargs):
            calls.append(kwargs)
            return pd.DataFrame({'Close': [len(calls)]})
        with tempfile.TemporaryDirectory() as directory, patch.dict('sys.modules', {'yfinance': types.SimpleNamespace(download=download)}):
            source = YahooSource(directory, mode='fetch', pause=0)
            source.history('FAKE')
            source.history('FAKE')
            self.assertEqual(len(calls), 1)
            YahooSource(directory, mode='fetch', pause=0, refresh=True).history('FAKE')
            self.assertEqual(len(calls), 2)
            self.assertTrue(calls[0]['keepna'])

    def test_tty_progress_clears_before_messages(self):
        class Terminal(io.StringIO):
            def isatty(self):
                return True
        with tempfile.TemporaryDirectory() as directory:
            output = Terminal()
            with RunLog('synthetic', directory, stream=output) as log:
                log.progress()
                log.message('durable message')
            self.assertIn('\r\x1b[2K', output.getvalue())
            self.assertIn('durable message', output.getvalue())

    def test_log_storage_failure_does_not_claim_a_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'file'
            root.write_text('occupied')
            with self.assertRaises(OSError):
                RunLog(root=root, stream=io.StringIO())
            self.assertFalse((root / 'agent-review').exists())

    def test_legacy_projection_does_not_mutate_capture_and_preserves_gap_true_range(self):
        from research_core.prices import clean_ohlcv, true_range
        frame = pd.DataFrame({'Open': [10, 15], 'High': [12, 17], 'Low': [9, 14], 'Close': [11, 16], 'Volume': [3, 4]})
        frame.columns = pd.MultiIndex.from_tuples([(x, 'FAKE') for x in frame.columns])
        original = frame.copy()
        cleaned = clean_ohlcv(frame)
        self.assertEqual(true_range(cleaned).tolist(), [3.0, 6.0])
        pd.testing.assert_frame_equal(frame, original)

    def test_converter_schema_failure_keeps_previous_output(self):
        from parquet_to_compact_csv import convert_directory
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'a.parquet').touch()
            (root / 'b.parquet').touch()
            output = root / 'output.csv.gz'
            output.write_bytes(b'previous')
            frames = [pd.DataFrame({'x': [1]}), pd.DataFrame({'y': [2]})]
            with patch('pandas.read_parquet', side_effect=frames), self.assertRaisesRegex(ResearchError, 'PARQUET_SCHEMA_MISMATCH'):
                convert_directory(root, output)
            self.assertEqual(output.read_bytes(), b'previous')

    def test_cli_help_and_invalid_arguments_do_not_create_logs_or_read_credentials(self):
        import tradier_iv_collector
        import os
        original_get = os.environ.get
        def guarded_get(key, default=None):
            if 'TOKEN' in key or 'SECRET' in key:
                raise AssertionError('credential lookup forbidden')
            return original_get(key, default)
        with tempfile.TemporaryDirectory() as directory, patch('os.environ.get', side_effect=guarded_get), patch('research_core.runtime.RunLog', side_effect=AssertionError('help must not create logs')), patch('sys.stdout', io.StringIO()), patch('sys.stderr', io.StringIO()):
            with patch('sys.argv', ['tradier_iv_collector.py', '--help']), self.assertRaises(SystemExit) as result:
                tradier_iv_collector.main()
            self.assertEqual(result.exception.code, 0)
            with patch('sys.argv', ['tradier_iv_collector.py', '--invalid-flag']), self.assertRaises(SystemExit) as result:
                tradier_iv_collector.main()
            self.assertEqual(result.exception.code, 2)

    def test_logged_partial_operation_returns_nonzero(self):
        from research_core.runtime import logged_main
        with tempfile.TemporaryDirectory() as directory:
            real = RunLog('synthetic', directory, stream=io.StringIO())
            @logged_main
            def operation(log):
                log.progress(success=True)
                log.progress(success=False)
            with patch('research_core.runtime.RunLog', return_value=real):
                self.assertEqual(operation(), 1)
            self.assertEqual(json.loads(real.report_path.read_text())['stage'], 'partial')

    def test_empty_captures_fail_consistently_on_fetch_and_replay(self):
        fake = types.SimpleNamespace(download=lambda *a, **kw: pd.DataFrame())
        with tempfile.TemporaryDirectory() as directory, patch.dict('sys.modules', {'yfinance': fake}):
            with self.assertRaisesRegex(ResearchError, 'PUBLIC_FETCH_EMPTY'):
                YahooSource(directory, mode='fetch', pause=0).history('FAKE')
            with self.assertRaisesRegex(ResearchError, 'PUBLIC_FETCH_EMPTY'):
                YahooSource(directory).history('FAKE')

    def test_interrupted_capture_never_shadows_previous(self):
        frame = pd.DataFrame({'Close': [4.0]})
        with tempfile.TemporaryDirectory() as directory:
            store = CaptureStore(directory)
            store.save({'kind': 'synthetic'}, frame)
            with patch('pathlib.Path.write_bytes', side_effect=OSError('interrupted')):
                with self.assertRaises(OSError):
                    store.save({'kind': 'synthetic'}, pd.DataFrame({'Close': [8.0]}))
            pd.testing.assert_frame_equal(store.load({'kind': 'synthetic'}), frame)
            self.assertEqual(len(list(Path(directory).rglob('*.json'))), 1)

    def test_bounded_json_capture_and_error_classification(self):
        from research_core.fetching import fetch_json
        class Response:
            def __init__(self, body):
                self.body = body
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def raise_for_status(self):
                pass
            def iter_content(self, chunk_size):
                yield self.body
        for body, code, status in [(b'broken', 'PROVIDER_INVALID_JSON', 'invalid_json'),
                                   (b'{"errors":"private"}', 'PROVIDER_INVALID_PAYLOAD', 'invalid_payload')]:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                session = types.SimpleNamespace(get=lambda *a, **kw: Response(body))
                with self.assertRaisesRegex(ResearchError, code):
                    fetch_json(session, 'https://example.invalid', {}, directory)
                metadata = json.loads(next(Path(directory).glob('*.json')).read_text())
                self.assertEqual(metadata['acquisition_status'], status)
                self.assertEqual(next(Path(directory).glob('*.body')).read_bytes(), body)
        with tempfile.TemporaryDirectory() as directory:
            session = types.SimpleNamespace(get=lambda *a, **kw: Response(b'too large'))
            with self.assertRaisesRegex(ResearchError, 'RESPONSE_TOO_LARGE'):
                fetch_json(session, 'https://example.invalid', {}, directory, max_bytes=3)
            self.assertEqual(list(Path(directory).iterdir()), [])
