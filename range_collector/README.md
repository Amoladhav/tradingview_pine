# Adaptive X-day range: expanded research collection

## Setup (Windows PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:TRADIER_TOKEN = 'YOUR_LIVE_TRADIER_ACCESS_TOKEN'
python collect.py --out range_output --start 2015-01-01
```

**Important:** Tradier sandbox market quotes may be delayed/static; use a live-market-data entitlement for a meaningful spread screen. Run during regular market hours, preferably on multiple days. Never share your token. Historical OHLC comes from Yahoo Finance via `yfinance`, not Tradier. Check provider terms and corporate-action adjustments.

### Test SOXL first

```powershell
python collect.py --only SOXL --out test_soxl --start 2015-01-01
```

### Collect ETFs only (no token needed)

```powershell
python collect.py --skip-stocks --out etf_data
```

### Manually supply 20 stocks (bypass options-liquidity ranking)

Create `stocks.csv` with `symbol,sector` headers, then:

```powershell
python collect.py --stocks-file stocks.csv --out manual_data
```

### How stock selection works

- Interpret “S&P 200” as the **largest 200 current S&P 500 constituents by market capitalization**; this is a current snapshot and introduces survivorship bias for older years.
- Rank candidates on near-ATM call/put contracts at ~7 and ~35 calendar DTE, requiring >=6 valid contracts, median quoted relative spread <=20%, aggregate sampled volume >=100 and OI >=500.
- Rank eligible names by volume, OI and tightness, then reproducibly random-sample 20 from the top 80 using seed 20261010.
- `top200.csv`, `liquidity.csv`, `eligible_ranked.csv`, and `selected_20.csv` preserve the audit trail. `liquidity.csv` is a snapshot; for robust screening repeat on several trading days and aggregate before selecting.
- Do not interpret a single snapshot as proof of historical options liquidity. Option liquidity is used only to select symbols, not as a predictive feature.

### Files

Per-symbol `*_anchors.csv.gz` and `*_outcomes.csv.gz`, with column names matching the uploaded tables; `manifest.csv` reports success/errors. Outcomes include horizons 1..60 by default. No synthetic ETF earnings events are generated. SOXL is mandatory in the default ETF cohort.

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
