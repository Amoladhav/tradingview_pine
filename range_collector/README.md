# Adaptive X-day range: expanded research collection

## Setup and execution

Install the shared Python dependencies using the repository [setup guide](../docs/SETUP.md).
Run commands from the repository root with the selected virtual-environment interpreter.
The directory requirements file delegates to the shared requirements.

By default, collection replays the exact request from the shared local capture cache;
a cache miss fails without network access. Add `--fetch` explicitly for an owner-run
public download. Captures preserve the decoded yfinance table before filtering;
they are not raw Yahoo response bytes. Daily prices retain `auto_adjust=True`.

```bash
python range_collector/collect.py --only SOXL --out range_output --start 2015-01-01 --fetch
python range_collector/collect.py --only SOXL --out range_replay --start 2015-01-01
python range_collector/collect.py --stocks-file stocks.csv --out manual_data --fetch
```

`--cache-dir` selects private cache storage. `--only` bypasses all universe
selection, including a supplied stock CSV. Without `--only` or `--select-stocks`,
the default is the existing ETF basket; `--stocks-file` adds a CSV with a `symbol`
column and optional `sector` column. `--skip-stocks` remains compatible.

Automatic stock discovery now requires **both** `--select-stocks --fetch`.
This legacy path uses a user-managed `TRADIER_TOKEN` and may contact Wikipedia,
Yahoo and Tradier. Only the owner may execute it. It retains the old selection
formulas; its Wikipedia, market-cap and Tradier capture/profile migration is
pending. Those paths do not yet provide the shared history adapter's immutable
capture or replay guarantees. Existing selection snapshots are reused without a
freshness guarantee. Missing credentials fail rather than selecting a substitute
cohort. Configure credentials locally; never paste them into source or chat.

### How stock selection works

- Interpret “S&P 200” as the **largest 200 current S&P 500 constituents by market capitalization**; this is a current snapshot and introduces survivorship bias for older years.
- Rank candidates on near-ATM call/put contracts at ~7 and ~35 calendar DTE, requiring >=6 valid contracts, median quoted relative spread <=20%, aggregate sampled volume >=100 and OI >=500.
- Rank eligible names by volume, OI and tightness, then reproducibly random-sample 20 from the top 80 using seed 20261010.
- `top200.csv`, `liquidity.csv`, `eligible_ranked.csv`, and `selected_20.csv` preserve the audit trail. `liquidity.csv` is a snapshot; for robust screening repeat on several trading days and aggregate before selecting.
- Do not interpret a single snapshot as proof of historical options liquidity. Option liquidity is used only to select symbols, not as a predictive feature.

### Files

Per-symbol `*_anchors.csv.gz` and `*_outcomes.csv.gz`, with column names matching the uploaded tables; `manifest.csv` reports success and sanitized error codes. Shared run logs and allowlisted review reports live under `artifacts/`; a partial run exits nonzero. Files are replaced atomically, but an anchor/outcome pair is not a multi-file transaction; consult the current manifest before reuse. Outcomes include horizons 1..60 by default. No synthetic ETF earnings events are generated. SOXL is mandatory in the default ETF cohort.

### Research caveats requiring explicit checks before pooling

1. **Feature definitions may not exactly match the earlier collector.** This script supplies transparent candidate definitions (Wilder ATR, normalized slope, past-close zone hit rate), but the original pipeline's formulas were not provided. Before concatenating, compare overlapping AAPL or other reference symbols and reconcile feature semantics. Column-name equality is NOT proof of feature equivalence.
2. Yahoo `auto_adjust=True` adjusts the entire OHLC series consistently for splits/dividends. This avoids artificial splits in ATR and returns but can differ from raw tradeable prices and from your original dataset. Verify overlap before combining.
3. Excursion labels use future daily **high/low**, terminal uses future daily close. An X-day label is omitted unless X complete future sessions exist.
4. Current S&P membership is survivorship-biased; this cohort is intended as a liquidity-focused external validation sample, not a replacement for a survivorship-free historical universe.
5. ETFs, especially daily-reset leveraged SOXL, should be reported separately and must not inherit an equity earnings model. SOXL's historical splits and leverage resets need additional checks.
6. The script keeps genuine tail events and does not winsorize. The latest X trading days necessarily lack complete outcome labels.
7. Data downloads can be rate-limited or fail. Review `manifest.csv`; rerun failures with `--only`.
8. `--end` is an **exclusive** date for yfinance. Data timestamps are daily exchange sessions.
9. This collector does **not** prove model improvements; run chronological holdouts and clustered/block confidence intervals on the new cohort.

## Verification boundary

Synthetic offline regressions cover complete future-session labels, earlier-feature
stability after changing future prices, invalid horizons and insufficient history.
The optimized rolling-window excursion computation retains the original label
semantics. Provider downloads, authenticated selection, cross-platform runtime,
corporate-action handling and research-performance acceptance remain pending.
Pine code and alert behavior are unchanged.
