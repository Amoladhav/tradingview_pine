# Python research framework

The Python tools share a small library rather than a web service or scheduler.
`pyproject.toml` owns dependencies and installed command names. Existing source
paths remain usable; `python_scritps/` retains its established spelling.

## Boundaries and extension points

| Layer | Location | Responsibility |
| --- | --- | --- |
| Provider/capture | `python_scritps/research_core/` | Explicit fetch, immutable decoded captures, cache replay, safe failures and progress |
| Existing studies | `python_scritps/*.py` | Existing daily/adaptive calculations and conversion entry points |
| Daily and intraday collectors | `range_collector/`, `intraday_collector/` | Collector-specific inputs, calculations and output schemas |
| Weekly RSI | `python_scritps/rsi_research/` | Daily-to-weekly aggregation, predictor features, separate future outcomes and paths |
| CLI | Installed `research-*` commands | Parse settings and invoke reusable Python functions |
| Verification | `tests/`, `tools/test_research_offline.py` | Synthetic calculations, cache failure/replay and isolation checks |

A new study should consume a captured table through the shared source interface,
then call pure calculation functions. Add provider-specific code behind that
interface; do not copy downloader loops into another study. There is no plugin
loader, daemon, hosted worker or web interface. Future interfaces should reuse
these services and validation rather than duplicate business rules.

## Commands and complete source

| Command | Canonical source |
| --- | --- |
| `research-rsi-weekly` | [rsi_weekly_study.py](../python_scritps/rsi_weekly_study.py) |
| `research-directional` | [directional_range_study.py](../python_scritps/directional_range_study.py) |
| `research-adaptive` | [build_adaptive_range_dataset.py](../python_scritps/build_adaptive_range_dataset.py) |
| `research-earnings` | [download_earnings_dates.py](../python_scritps/download_earnings_dates.py) |
| `research-compact-csv` | [parquet_to_compact_csv.py](../python_scritps/parquet_to_compact_csv.py) |
| `research-range` | [collect.py](../range_collector/collect.py) |
| `research-intraday` | [collect_intraday.py](../intraday_collector/collect_intraday.py) |
| `research-tradier-iv` | [tradier_iv_collector.py](../python_scritps/tradier_iv_collector.py) |

## Platform-neutral implementation and handoff

Application behavior uses Python paths, file operations and archiving rather than
requiring Bash or Unix utilities. Setup commands differ between PowerShell and
Linux shells; the Python arguments and calculation functions stay the same.
Windows and Linux execution must be tested separately before claiming support.

The present deliverable is reproducible research data for the owner's handoff to
ChatGPT for indicator logic. Share the intended study outputs, dictionary,
methodology and source archive after reviewing their contents. Keep credentials
and private caches excluded. Pine v6 implementation can also be done in this
repository when requested; compilation and chart acceptance still require
TradingView evidence. No new Pine implementation is authorized by this Python phase.

## Fetch and replay

Yahoo consumers default to cache-only execution. `--fetch` explicitly permits
public Yahoo requests and reuses matching captures; refresh behavior is controlled
by `--fetch --refresh`. A cache miss fails safely rather than fetching implicitly.
Never run an entire universe merely to test setup: history collection can take a
long time and provider limits can produce partial results.

Private captures live under ignored `artifacts/private/`. They preserve the full
**decoded yfinance DataFrame boundary**, including fields not used by a study.
They are not raw Yahoo response bytes: yfinance can transform values before the
application receives them. Captures and derived research files are separate;
replay does not require another download. A provider-returned table does not prove
complete coverage. Review missingness and per-symbol failures before analysis.

The existing Tradier liquidity/IV routes remain explicitly user-run credentialed
operations. The presence of a token does not authorize an agent to execute them.
Wikipedia constituent discovery and market-cap selection are legacy adapter paths;
they do not yet establish the complete capture/profile/normalization contract.
Provider adoption and live acceptance must be reported separately.

Cache files are user-local research data and are excluded from source archives.
No automatic retention/deletion is configured. The owner controls retention and
filesystem access. Do not upload captures, credential stores or arbitrary logs to
an agent; use the intended sanitized aggregate review reports.

## Compatibility and intentional changes

- Existing Pine files are outside this increment.
- Existing study formulas retain their definitions; do not pool different
  collectors merely because column names match.
- Yahoo downloads now require `--fetch` when the exact request is not cached.
- The directional study writes `directional_universe.csv` instead of overwriting
  the owner's unrelated root `universe.csv`.
- Earnings now defaults to the directional study's `directional_excursions.csv`.
  Existing compressed inputs remain supported with
  `--input directional_excursions.csv.gz`; output and coverage paths are explicit
  `--output` and `--coverage` options.
- Root `pyproject.toml` replaces independently maintained dependency lists.
  Collector requirements files are compatibility pointers; install from the root.
- Sandbox IV collection now requires `--fetch` and no longer automatically
  retries authenticated requests. Tradier liquidity and discovery remain legacy
  ingestion paths; sandbox IV body capture does not establish their adoption.
- Shared logs currently report `code_revision="unrecorded"` and `profile="local"`;
  do not treat that placeholder as verified Git provenance.
- A failed/partial acquisition is reported separately from successful symbols.
  Offline cache success is not a live provider acceptance result.

See [RSI methodology](RSI_STUDY.md), [setup](SETUP.md), and
[verification](VALIDATION.md). The RSI study generates research measurements;
it does not select strategies, optimize thresholds or establish predictive value.

## Dependencies and references

Direct dependencies are pinned to the versions present in the reviewed local
environment. This is not a complete transitive lock or a claim that every target
OS has compatible wheels. Python 3.12+ is required by the selected numerical
packages; current execution evidence is Python 3.14.4 on Linux only.

Packaging follows [setuptools' pyproject configuration](https://setuptools.pypa.io/en/latest/userguide/pyproject_config.html).
The Yahoo adapter explicitly controls adjustments and dates; the provider wrapper
specifies an [exclusive end date](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html).
RSI uses the recursive RMA definition described by
[TradingView](https://www.tradingview.com/pine-script-docs/migration-guides/to-pine-version-5/);
identical chart/provider history and owner-run parity checks are still required.
