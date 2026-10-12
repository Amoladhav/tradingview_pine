# Python research delivery plan

Updated: 2026-10-11.

## Present scope

Reorganize repeated Python fetching/dependency/error-handling code into a shared,
extensible local framework. Preserve existing source paths and calculation
contracts. Add the requested weekly RSI/SMA research dataset without strategies,
optimized thresholds, buy/sell recommendations or performance claims.

The weekly study uses daily observations as its source of truth. Completed weekly
predictors are separated physically from future outcomes and event paths.
Continuous measurements remain available alongside descriptive flags. An
approximately 100–150-symbol current US equity/ETF universe is intentionally
survivorship-biased at this exploratory stage; record the actual requested and
successful symbols and their coverage. Later IPOs are not exclusion criteria.

The owner intends to hand the generated research data to ChatGPT for indicator
logic. A later explicitly requested Pine implementation may also be developed in
this repository, with owner-run TradingView acceptance. Agents explain Python
choices during development and target platform-neutral Windows/Linux behavior;
these preferences are recorded in `AGENTS.md`.

## Requirement groups and acceptance

| Requirement | Implementation location | Acceptance gate |
| --- | --- | --- |
| Reusable capture/replay/error/progress | `research_core/` | Synthetic preservation, replay, failures, safe diagnostics |
| Existing daily/intraday studies | Existing entry points | Offline regression coverage; owner live comparison still required |
| Universe/history/adjustments | RSI CLI and weekly aggregation | Coverage and adjustment metadata; owner checks sample symbols |
| RSI14 / RSI SMA5,8,10,14,21 | RSI pure features | Hand-calculated seed/recursion tests; TradingView parity pending |
| Crossovers, slopes, geometry, zones, shape | RSI pure features | Causal prefix tests, known crosses, documented windows/pivots |
| Price, volatility, volume, candle, daily detail | RSI pure features | Synthetic formulas and null/zero behavior; inspect dictionary |
| SPY/QQQ/IWM and sector context | RSI pipeline joins | Same-week joins only, missing context remains explicit |
| Historical earnings | Optional separate source | Omitted until a reliable historical source is established |
| Forward outcomes / move structure / paths | RSI outcomes | Event-week exclusion, full-horizon flags, censoring and signs |
| CSV.gz, dictionary, metadata, summary, archive | RSI export | Offline end-to-end outputs and exact archive allowlist |
| Portability and live provider behavior | Owner-run acceptance | Separate native Windows, WSL, Ubuntu, macOS records |

See [RSI_STUDY.md](RSI_STUDY.md) for precise formulas, caveats and commands, and
[STATUS.md](STATUS.md) for actual verification. This matrix states intended
acceptance; it is not evidence that the live study or Pine parity has passed.

## Decisions

Use pandas/NumPy and standard-library argparse, functions and package
metadata. A local library with thin CLI entry points is sufficient for the current
workload. New provider adapters and studies can reuse it without a service,
framework server or plugin loader. Do not build future UI or scheduling now.

Retain legacy paths to avoid breaking working references. Consolidate dependencies
in `pyproject.toml`; compatibility requirements files delegate to it. Make public
fetching explicit, preserve decoded provider tables before projection, and expose
cache replay so a feature change does not require another acquisition.

Completed weeks use a conservative date cutoff rather than assuming the wall
clock means the exchange has closed. Holiday weeks aggregate observed sessions;
missing-session detection still needs an authoritative exchange calendar before
completeness can be certified. Acquisition success and session completeness are
separate states.

## Next increments after owner review

1. Run a small owner-led public collection and inspect the sanitized summary and
   hand-checked AMZN, AAPL, MSFT, JPM, XOM and SPY examples.
2. Compare weekly RSI/SMA on identical histories and adjustment settings with
   TradingView; record tolerances and warm-up boundaries.
3. Extend session-calendar validation, adapter field profiling and cross-run
   schema-drift reporting where the current evidence identifies gaps.
4. Validate dependency installation and CLI execution separately on every target
   OS; introduce a transitive lock only after those environments are reconciled.
5. Review historical earnings provenance and point-in-time availability before
   joining any calendar-derived predictors. Realized future earnings dates cannot
   become historical predictors without evidence of their known-at-event state.

No future step activates hosted CI, credentialed workers or provider operations.
