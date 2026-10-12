# Weekly RSI research dataset

This is data collection and descriptive feature generation, not a trading strategy.
No threshold optimization, trade recommendations, or success/failure labels are
implemented. The default universe has diversified equities and broad/sector ETFs;
the actual requested, usable and failed symbols are saved in every run's metadata.
The explicit list and sector comparators live in `rsi_weekly_study.py`. It is a
present-day selection, not historical index membership: survivorship bias applies.
Sector comparators are manually assigned study inputs, not provider classifications.

## Run boundaries and reproducibility

The entry point is `python_scritps/rsi_weekly_study.py`. The pure implementation is
`python_scritps/rsi_research/`; shared source/cache/progress code lives in
`python_scritps/research_core/`. Install dependencies using `docs/SETUP.md`.
No fetch occurs by default. A new output directory is required on every invocation.
These commands use a deliberately fixed cutoff so a replay requests the same cache
key; replace the date explicitly for a different study cutoff.

```bash
python python_scritps/rsi_weekly_study.py --as-of 2026-10-11 --output-dir artifacts/rsi_replay
```

The owner may explicitly download public data (this can require hundreds of
requests and substantial time; per-symbol progress is shown):

```bash
python python_scritps/rsi_weekly_study.py --fetch --as-of 2026-10-11 --output-dir artifacts/rsi_fetch --show-samples
```

`--symbols SPY AAPL AMZN MSFT JPM XOM` permits a smaller manual acceptance run.
The same Python arguments work in PowerShell with its separately installed Python
interpreter. No authenticated provider operations are required or authorized.
`--show-samples` writes a separate owner-review CSV rather than putting symbol data
in operational logs. No live research files were fetched during implementation.

`--start` defaults to 2005-01-01. A later IPO remains eligible. `--as-of` is an
exclusive daily-date cutoff; future cutoffs are rejected. Every Friday label must
also be strictly before that cutoff. Thus the current week becomes eligible on
Saturday, including holiday-shortened weeks; Friday after-close runs conservatively
wait until Saturday. This is an explicit date rule, not an exchange-calendar service.
Missing intraweek sessions remain visible in `trading_days`; exchange-calendar
completeness remains unverified. Weekends, duplicate dates, missing entire weeks,
invalid/missing OHLCV and inconsistent candle geometry quarantine that symbol from
features. The source capture remains available, and valid symbols continue.

Fetches request daily data with `auto_adjust=False` and `actions=True`. The shared
cache preserves all decoded returned fields before research projection, including
corporate actions and unknown fields. It does not claim original Yahoo wire JSON.
Feature engineering does not refetch in cache mode. Source cache keys include date
and adjustment settings; requesting different settings requires a matching capture
or an explicitly requested fetch. No silent fallback, retry or scheduling occurs. `--fetch` may reuse matching captures;
`--refresh` explicitly requests new acquisition with otherwise identical settings.

## Price, dates and weekly construction

Timezone-aware daily indices are converted to America/New_York, then normalized
to calendar dates. Naive daily indices are interpreted as exchange-local dates.
Only Monday-Friday observations are accepted. Pandas `W-FRI` labels normal US weeks:
open=first open, high=max(high), low=min(low), close=final close, volume=sum(volume),
adjusted close=final daily adjusted close including missingness. Holidays are not
filled. Partial current weeks remain in daily source exports but not weekly features.

All primary RSI, price features and outcomes consistently use the source `Close`
and source OHLC, not `Adj Close`. No additional split or dividend adjustment is
performed. The separate provider `Adj Close`, dividends and split fields are
retained when supplied. Provider `auto_adjust=False` does not establish unadjusted
historical share prices or exact corporate-action semantics; its returned OHLC may
already be split adjusted. Provider behavior and parity with the selected
TradingView chart adjustment setting require live owner verification. Dividend-
adjusted research can be added as an explicitly versioned calculation basis later;
it must not mix adjusted close with unadjusted high/low for excursions.

## Formula conventions

All predictor windows include the current completed weekly bar unless called
`prior` or `previous`. Full windows are required; warmup remains NA. Divisions by
zero remain NA. Return fractions are decimal values (0.01 = 1%); `atr_percent_N`
is explicitly percent. Percentile is an empirical rank, never a probability.
Calculations retain floating-point precision without discretionary rounding.

- RSI14: delta=close-prior close; gains=max(delta,0), losses=max(-delta,0).
  RMA14 is seeded with the mean of the first 14 valid changes, then updated as
  prior RMA + (observation-prior RMA)/14. Missing changes do not advance its state
  and yield NA at that observation. RSI=100 if average loss=0, else 0 if gain=0,
  else 100-100/(1+gain/loss). The user's specified loss-zero branch wins a flat
  tie (RSI=100); TradingView parity for degenerate flat inputs remains pending.
- `rsi_sma_N`: arithmetic mean of RSI14 over N=5,8,10,14,21 observations.
  Spread=RSI14-SMA14(RSI14). Cross direction=1 when spread changes from <=0 to >0,
  -1 when it changes from >=0 to <0, otherwise 0. Every primary SMA14 cross is kept.
- `*_previous_N` and `*_change_N`: lagged value and current minus N-week lag.
  Endpoint slope_N=(current-value N-1 weeks ago)/(N-1). OLS slope uses x=0..N-1
  centered on its mean: sum(centered x * y)/sum(centered x squared). Units are
  points/week or price/week. Price normalized slope divides by current close.
  Slope change is its first difference; strengthening compares absolute magnitude
  with the preceding slope, not whether it has a favorable direction.
- SMA slope sign change uses signs of first differences; zero is a distinct sign.
  Weeks since change measures positional weekly distance to the most recent change.
  Cross velocity_N=(RSI OLS slope_N - RSI-SMA OLS slope_N)/100, not a visual angle.
- Spread lags and absolute spread preserve continuous values. Maximum absolute
  spread since prior cross covers that cross through the week before the event.
  Previous-side duration counts the immediately prior equal-sign nonzero run.
  Prior crossing counts exclude the current bar. Unknown first-cross history is NA.
- RSI zone flags have inclusive bounds, so adjacent bins overlap at boundaries;
  <20 and >80 are strict. Distances subtract 30,40,50,60,70 without interpretation.
- Trailing extrema/ranges use N=4,8,13,26; percentile=fraction of window values
  <=current. Weeks since extrema chooses the most recent tied extreme. RSI, RSI
  SMA and price pivots use strict one-bar-left/one-bar-right extrema: a pivot at
  t-1 becomes available only at t. Latest/previous confirmed values, their
  difference, and higher/lower flags remain available. No future pivot enters t.
- Price return_N=close/close_N_weeks_ago-1 for 1,2,4,8,13,26,52 weeks. Distances
  to highs/lows are close/trailing extreme-1. Price high/low changes are first
  differences of rolling extrema. Price SMA10/20/40/50 and relative distances,
  first differences and second differences remain separate, with no trend label.
- TR=max(high-low,abs(high-prior close),abs(low-prior close)); first TR=high-low.
  ATR5/14/21 uses SMA-seeded Wilder RMA. ATR percent=100*ATR/close. Expansion is
  current ATR_N divided by the mean of N strictly prior ATR_N observations.
  Realized volatility_N=sample stdev(weekly simple returns,N)*sqrt(52), for
  4,8,13,26,52. Volatility ratios compare current/prior same statistic. Volatility
  percentiles rank 13-week realized volatility against 52,104,156-week windows.
- Volume averages/relative volume include the current week. Percentiles use
  26,52,104 weeks. Robust z26=(volume-median26)/(1.4826*median absolute deviation26),
  NA when MAD=0. Price change, absolute change and TR per volume are retained;
  normalized variants divide the measurement by ATR14 and relative volume13.
  Previous 1..4 volumes and relative volume13 values capture pre-event behavior.
- Body=close-open; range=high-low; upper wick=high-max(open,close);
  lower wick=min(open,close)-low. Fractions divide by range. Close location is
  (close-low)/range; directional efficiency=abs(body)/range. Gap=open-prior close.
  ATR-normalized body/range/return divide body, range or close change by ATR14.
  Body/ATR times relative volume13 is an additional continuous interaction.
- Daily substructure uses daily close returns, including Monday versus prior
  observed Friday. Up/down counts exclude zero returns. Daily realized volatility
  is sample stdev without annualization. Largest up/down returns require the
  appropriate sign (otherwise NA). High/low weekday uses the first tie, Monday=0.
  Daily volume_1..5 is volume on each observed trading date, preserving raw values.
- Market features join SPY/QQQ/IWM on the same Friday only, without forward fill.
  Missing benchmark data stays missing. Relative performance_N is the symbol's
  simple N-week return minus the benchmark's for N=4,13,26,52. Sector comparator
  mapping is explicit; no market regime label is inferred.

## Outcomes and censoring

Predictor and future tables are physically separate. No outcome is used to select
crosses. Event identifiers combine symbol, Friday date and formula revision.

Forward horizons are 1,2,3,4,6,8,13,26,39,52 weeks. Return=close at horizon/event
close-1. Excursions use **only following bars**, offsets 1..N. For bull events,
favorable=max(0,max high-event close), adverse=min(0,min low-event close).
For bear events, favorable=max(0,event close-min low), adverse=min(0,event
close-max high). MFE is nonnegative; MAE is signed nonpositive. Fractions divide
by event close; ATR variants divide by event-week ATR14. High/low and first offset
to those extremes are retained. No entry price, fees, slippage or profitability
claim is implied by measurement from a completed event close.

`complete_N=false` makes all N-horizon measurements NA when fewer than N future
weeks exist; partial horizons are never compared as if complete. The next-opposite
cross fields use following bars **through that opposite-cross week inclusive**;
without an observed opposite cross the fields remain NA and the censor flag is
false. Equal spread can lead to repeated same-direction crosses, so the next
opposite cross is searched by direction rather than assuming event alternation.

First-hit offsets use future highs for +0.5,+1,+1.5,+2,+3,+4 event ATR and future
lows for corresponding negative thresholds, without imposing a within-week order
when both thresholds hit. Search is capped at 52 weeks. NA means no observed hit;
`path_complete_52` distinguishes a full search from censoring. Paths retain each
available future week up to 52, OHLC returns and ATR offsets, RSI, RSI-SMA and spread.
Historical earnings are omitted because a reliable complete history is not yet
established. Future earnings dates must never be added as causal predictors
without point-in-time announcement provenance.

## Artifacts and checks

The run writes the five requested compressed daily/weekly/event/outcome/path tables,
`rsi_data_dictionary.csv`, metadata JSON and summary text. The dictionary covers
every emitted column, units, formula family and predictor/source versus future
role. Unknown provider fields are retained with their semantics explicitly
unverified. Metadata records failures, package versions, universe, date rule and
calculation warnings. Summary counts include bulls/bears, year/decade/sector,
coverage and missing values (including legitimate warmup/censoring).

The exact generated files, source modules, pinned dependency list, archive run instructions, this specification,
and a snapshot of that run's logs are packaged into
`rsi_sma_weekly_study.tar.gz`. Caches, credentials, environments and unrelated files
are excluded. The packaged logs end before archive completion; the final status and
sanitized review report remain beside the archive in the run log directories.
Completed runs print `STUDY COMPLETE` and archive path/size. A usable
subset with symbol failures prints `STUDY PARTIAL` and exits 2; no usable symbols
fails without claiming a successful dataset. Output/packaging failure is an error.

Offline tests exercise the RMA seed, recursive updates, rising/falling/flat RSI,
completed-week aggregation, causal suffix mutation, horizon extrema/censoring,
partial-symbol isolation and artifact schema. They do not verify Yahoo data,
TradingView compilation/parity, missing exchange sessions or strategy value.
Run the guarded suite from repository root:

```bash
.venv/bin/python -I -S tools/test_research_offline.py --pattern 'test_rsi*.py'
```

Live manual acceptance remains pending for AMZN, AAPL, MSFT, JPM, XOM and SPY,
including split/dividend dates and matching chart adjustments. Native Windows,
WSL, native Ubuntu and macOS acceptance are separate pending gates.
