# Verification checklist

## For every Pine change

1. Review the exact diff. Classify calculation, display, alert and timeframe effects.
2. Check Pine v6 declaration, indentation/continuations, identifiers, types and
   scopes; review relevant built-in signatures against official Pine documentation.
3. Review series/history indexing, warm-up and `na`, zero denominators, empty or
   bounded arrays, loops and drawing-object limits along each changed path.
4. Inspect `request.*`, gaps/lookahead, bar confirmation, intrabar updates, frozen
   timeframe options, timezone/session boundaries and historical versus realtime
   behavior. Confirm whether current observations enter reference populations.
5. Preserve input defaults and alert names/conditions unless the requested change
   explicitly alters them. Explain units and changed statistical assumptions.
6. Run `git diff --check`, review Markdown links, and perform a value-suppressing
   scan of exact staged content before committing. Report scan limits. No scanner
   or compiler is bundled here; unavailable required checks block a commit.
7. Compile and exercise the complete script in TradingView (owner-run). Record
   actual evidence separately from static review; do not infer compiler success.

No automated signal tests, local Pine compiler or hosted workflows are configured.
Documentation-only setup requires documentation/static repository checks, not a
claimed Pine compile-safety pass or synthetic tests that cannot execute Pine.

## TradingView acceptance

For each of the four scripts record date, Git commit, platform/browser, symbol and
exchange, chart type, timeframe, session, inputs and outcome. Keep account details
and private chart exports out of Git; report only intended sanitized observations.

- Compile, add to chart and check runtime errors with adequate history.
- Check default and changed inputs, show/hide settings and expected alert conditions.
- For the candle marker, check matching/nonmatching intraday bars, timezone/DST
  boundaries and daily charts; a bar must open at the selected time to match.
- For CCI, check warm-up, percentile bands, EMA crossings and degenerate price data.
- For both volume scripts, check intraday same-slot populations, daily/weekly/monthly
  aggregation, Fixed/Adaptive lookbacks, sparse history and missing/zero volume.
- Compare historical/replay and realtime behavior; record intended intrabar changes.
- Check identical source/settings on each target OS/browser. Compilation is shared
  through TradingView but local checkout, encoding and editor behavior still need
  platform evidence. A successful chart is not evidence of profitability.

## Platform acceptance record

| Environment | Clone/open UTF-8 source | Clean Git diff | TradingView compile/chart |
| --- | --- | --- | --- |
| Native Windows / PowerShell | Pending | Pending | Pending |
| WSL / Bash | Pending | Pending | Pending |
| Native Ubuntu / Bash | Pending | Pending | Pending |
| macOS / Terminal | Pending | Pending | Pending |

Setup-session Linux checks are recorded in STATUS; do not infer any row passed
without running the corresponding environment checks.
