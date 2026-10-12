"""Shared privacy-limited progress and structured run summaries."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import time
import uuid
from .errors import safe_error_code


class RunLog:
    def __init__(self, command='research', root='artifacts', total=None, stream=None):
        self.run_id = uuid.uuid4().hex
        self.command = command
        self.code_revision = 'unrecorded'
        self.profile = 'local'
        self.total = total
        self.stream = stream or sys.stdout
        self.started = time.monotonic()
        self.counts = {'attempted': 0, 'succeeded': 0, 'failed': 0}
        self.finished = False
        root = Path(root)
        logdir = root / 'logs'
        logdir.mkdir(parents=True, exist_ok=True)
        self.events_path = logdir / f'{self.run_id}.jsonl'
        self.errors_path = logdir / f'{self.run_id}.errors.jsonl'
        self.report_path = root / 'agent-review' / f'{self.run_id}.json'
        self._events = self.events_path.open('x', encoding='utf-8')
        self._errors = self.errors_path.open('x', encoding='utf-8')
        self._transient = False
        self.message(f'Logs: {self.events_path}; errors: {self.errors_path}')
        self._event('started')

    def _clear(self):
        if self._transient:
            self.stream.write('\r\x1b[2K')
            self._transient = False

    def message(self, message):
        self._clear()
        stamp = datetime.now().astimezone().isoformat(timespec='seconds')
        print(f'{stamp} {message}', file=self.stream, flush=True)

    def _event(self, stage, code=None):
        event = {'schema_version': 1, 'timestamp': datetime.now(timezone.utc).isoformat(),
                 'run_id': self.run_id, 'command': self.command, 'stage': stage,
                 'substep': stage, 'code_revision': self.code_revision, 'profile': self.profile,
                 'severity': 'error' if code else 'info', 'error_code': code,
                 'elapsed_seconds': round(time.monotonic() - self.started, 3),
                 'counts': self.counts.copy(), 'total': self.total}
        line = json.dumps(event) + '\n'
        self._events.write(line)
        self._events.flush()
        if code:
            self._errors.write(line)
            self._errors.flush()
        return event

    def progress(self, completed=None, total=None, *, success=True):
        self.counts['attempted'] += 1
        self.counts['succeeded' if success else 'failed'] += 1
        if total is not None:
            self.total = total
        self._event('progress')
        current = self.counts['attempted'] if completed is None else completed
        text = f'Processed {current}/{self.total if self.total is not None else "?"}; failed {self.counts["failed"]}'
        if self.stream.isatty():
            self._clear()
            width = max(20, shutil.get_terminal_size((80, 24)).columns - 1)
            self.stream.write('\r' + text[:width])
            self.stream.flush()
            self._transient = True
        else:
            self.message(text)

    def error(self, exc):
        code = safe_error_code(exc)
        self._event('error', code)
        self.message(code)

    def finish(self, status=None):
        if self.finished:
            return
        status = status or ('failed' if self.counts['failed'] and not self.counts['succeeded'] else 'partial' if self.counts['failed'] else 'completed')
        event = self._event(status)
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(json.dumps(event, indent=2) + '\n', encoding='utf-8')
        self.message(f'{status}: attempted={self.counts["attempted"]} succeeded={self.counts["succeeded"]} failed={self.counts["failed"]}; elapsed={event["elapsed_seconds"]}s')
        self.message(f'Logs: {self.events_path}; errors: {self.errors_path}; review: {self.report_path}')
        self._events.close()
        self._errors.close()
        self.finished = True

    def __enter__(self):
        return self

    def __exit__(self, kind, exc, traceback):
        successful_exit = isinstance(exc, SystemExit) and exc.code in (None, 0)
        if exc is not None and not isinstance(exc, (KeyboardInterrupt, SystemExit)):
            self.error(exc)
        self.finish('cancelled' if isinstance(exc, KeyboardInterrupt) else 'failed' if exc and not successful_exit else None)
        return False


def logged_main(function):
    """Create logs on first operational message, after CLI parsing succeeds."""
    from functools import wraps

    class LazyLog:
        def __init__(self):
            self.instance = None

        def __getattr__(self, name):
            if self.instance is None:
                self.instance = RunLog(command=function.__module__.split('.')[-1])
            return getattr(self.instance, name)

    @wraps(function)
    def wrapped(*args, **kwargs):
        log = LazyLog()
        try:
            result = function(log, *args, **kwargs)
        except SystemExit as exc:
            if log.instance is not None:
                log.instance.__exit__(SystemExit, exc, exc.__traceback__)
            raise
        except KeyboardInterrupt as exc:
            if log.instance is not None:
                log.instance.__exit__(KeyboardInterrupt, exc, exc.__traceback__)
            return 130
        except Exception as exc:
            if log.instance is not None:
                log.instance.__exit__(type(exc), exc, exc.__traceback__)
            print(safe_error_code(exc), file=sys.stderr)
            return 1
        if log.instance is not None:
            log.instance.finish()
            if log.instance.counts['failed']:
                return 1
        return 0 if result is None else result
    return wrapped
