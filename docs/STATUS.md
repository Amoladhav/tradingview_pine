# Project status

Updated: 2026-10-11.

## Identifier cleanup

Added versioned pre-commit/pre-push cleanup for literal `*.Identifier` files and a
`git stage-clean` staging alias. Git has no staging hook; ordinary add/GUI staging
still relies on the existing ignore rule and commit cleanup. Already indexed
matches block commits until their removals are staged. Push cleanup never changes
the index or committed history. Setup and boundaries are in `SETUP.md`.

No Pine/Python research calculations, displays, alerts, settings, timeframes or
historical results changed. Four offline synthetic tests passed in the current
Linux environment: recursive cleanup/boundaries, forced staging and commit
recovery, subdirectory staging, and direct push-hook cleanup with unchanged
index/history. Hooks and the staging alias are enabled in this checkout. No push
was executed. Shell syntax, diff whitespace and value-suppressing staged-content
review passed. Native Windows, WSL, native Ubuntu and macOS acceptance remain pending.

## Python research framework and RSI study

AGENTS now explicitly requires platform-neutral Windows/Linux Python, separate
platform validation and concise explanations of technical choices while working.
The current workflow produces research datasets for owner handoff to ChatGPT;
Pine implementation is a possible separately requested next phase.

Python-only implementation: dependency configuration in `pyproject.toml`, shared
`research_core` fetching/capture/cache/errors/progress and thin existing CLI entry
points. Source paths and existing daily research formulas are retained. Daily
forward-window calculations are reorganized for efficiency. Source captures precede
projection; they preserve decoded library tables rather than claiming Yahoo wire
fidelity. Public fetching is explicit (`--fetch`), cache-first, with intentional
refresh via `--fetch --refresh`. Credentials remain owner-run only.

New `rsi_research` modules implement the requested weekly study: daily-to-weekly
aggregation, SMA-seeded Wilder RSI, descriptive features, separate future outcomes
and paths, dictionary/metadata/summary and a bounded source/output archive. The
methodology, censoring, adjustment caveats and omission of unverified earnings are
in [RSI_STUDY.md](RSI_STUDY.md). No strategy labels or optimization were added.

Compatibility changes: `directional_universe.csv` protects the existing root
`universe.csv`; Yahoo calls require explicit fetching; automatic Tradier stock
selection requires `--select-stocks --fetch`; sandbox IV requests require
`--fetch`, and implicit API retries were removed. See
[PYTHON_RESEARCH.md](PYTHON_RESEARCH.md) and [RESEARCH_PLAN.md](RESEARCH_PLAN.md).

Verification: 51 guarded offline synthetic tests passed on Linux / Python
3.14.4, covering cache preservation/replay, CLI failures and credential isolation,
legacy numerical regressions, DST, RSI causality, horizons, empty schemas and
archive failure. The final source wheel built successfully with setuptools; all
eight entry-point modules are included. Python syntax, UTF-8, local Markdown
links and Git whitespace checks passed. Exact staged contents received a
value-suppressing scan before the local commit; this does not prove absence of
secrets. No live research dataset was acquired. Provider access, real
research results, chart RSI parity, native Windows, WSL, native Ubuntu and macOS
acceptance remain pending. No Pine code, calculations, displays, alerts, settings
or timeframe behavior changed; no TradingView compilation was attempted.

Known limits: direct dependency pins are not a transitive lock; system session
calendar completeness is not certified; capture profile comparisons are not yet
implemented; legacy Wikipedia/market-cap/Tradier liquidity discovery has not adopted
the full capture contract. Shared logs identify code revision as `unrecorded`
and profile as `local`; live provenance acceptance remains open. Captures/logs have
no automatic retention deletion. Hosted CI remains inactive.

## Earlier milestones (historical)

Adaptive Weekly Stress revision 1.02 check-in: adds Developing Weekly (default)
and Confirmed Weekly modes. Confirmed mode offsets all weekly outputs by one bar
and gates event signals on the start of a new weekly period. The dashboard shows
the selected mode; existing alert names remain unchanged, but their event timing
depends on the mode. User edits were preserved during check-in.
Staged whitespace and secret checks passed. TradingView compilation and chart /
alert acceptance remain pending, including chart intervals above one week; the
confirmed-mode non-repainting claim is not validated for those intervals.

Repository and agent bootstrap. Four existing Pine v6 indicators and two identical
prompt templates are retained with unchanged working-file bytes. There is no
application runtime, dependency installation, order service or active hosted CI.

Prepared: standalone AGENTS instructions (including shared policy revision 7),
README/script inventory, platform and publication guide, verification checklist,
Git ignores, line-ending/editor rules and initial source provenance manifest.

Both project prompt templates have been reconciled into explicit standing coding
instructions in AGENTS.md, including future non-Pine code where applicable,
frozen-timeframe limitations, tooltip guidance and complete delivery requirements.
The original templates and all Pine source remain unchanged.

## Bootstrap verification (historical)

Local Linux setup checks: original-source hash comparison, source inventory,
UTF-8/case/path review, relative documentation links, shared-policy copy comparison,
staged whitespace check and value-suppressing content scan. See the initial commit
for the reviewed snapshot. The scanner used for bootstrap is existing workspace
review tooling; it is not installed or enforced by this repository.

TradingView compilation, full Pine logic/compile-safety review, signal correctness,
repaint behavior and all four OS acceptance rows remain pending. No profitability
or cross-platform runtime claim is established by repository setup.

## Next steps

1. Owner reviews the baseline and confirms source ownership/attribution.
2. Owner creates a private remote and pushes using SETUP.md when ready.
3. Record TradingView acceptance for all ten indicators in `pine/` and platform smoke checks.
4. Choose a license before any public release; public publication is not authorized.
5. Make subsequent indicator changes in small commits using VALIDATION.md.

Python follow-up work is tracked in [RESEARCH_PLAN.md](RESEARCH_PLAN.md).
Deterministic Pine signal parity and multi-OS acceptance remain pending; hosted CI
requires separate explicit activation. Preserve one canonical Pine file per indicator.
