# TradingView Pine indicators

Standalone Pine Script v6 indicators live in `pine/`; Python research tools use
`python_scritps/` with daily/intraday collector entry points retained in their
existing folders. Git history tracks accepted source versions.

## Repository layout

- `pine/`: canonical indicators and the two retained project prompt templates.
- `python_scritps/`: research entry points, shared `research_core/`, and weekly
  `rsi_research/` calculations; preserve this folder spelling.
- `range_collector/`, `intraday_collector/`: daily and intraday collection.
- `pyproject.toml`: central dependencies, package configuration and CLI commands.
- `tests/`: synthetic offline Python research checks.
- `universe.csv`: local data file; schema, provenance and intended use are unreviewed.
- `docs/`: setup, status, validation and historical baseline notes.
- `.venv/`: optional ignored local Python environment, created separately per OS.

| Source | Indicator |
| --- | --- |
| [630 First Candle Marker.pine](pine/630%20First%20Candle%20Marker.pine) | Configurable intraday candle marker. |
| [ATR_Lines.pine](pine/ATR_Lines.pine) | ATR lines. |
| [ATR_Values.pine](pine/ATR_Values.pine) | ATR values. |
| [Adaptive_Stress.pine](pine/Adaptive_Stress.pine) | Adaptive Stress. |
| [Adaptive_Weekly_Stress.pine](pine/Adaptive_Weekly_Stress.pine) | Adaptive Weekly Stress. |
| [CCIEMA_percentile_extremes.pine](pine/CCIEMA_percentile_extremes.pine) | CCI, EMA signal and adaptive percentile extremes. |
| [Earnings_Range.pine](pine/Earnings_Range.pine) | Earnings Range. |
| [Price_Response_to_Volume.pine](pine/Price_Response_to_Volume.pine) | Price range/body response relative to comparable volume. |
| [Ratio_Adjusted_Summation_Index.pine](pine/Ratio_Adjusted_Summation_Index.pine) | Ratio-Adjusted Summation Index. |
| [Volume_Outlier_Profile.pine](pine/Volume_Outlier_Profile.pine) | Comparable-volume percentile, relative volume and robust outlier display. |

Descriptions identify the source; numerical and TradingView validation remain pending.
Python implementation and offline evidence are tracked separately in
[status](docs/STATUS.md); live provider, TradingView parity and platform acceptance
remain pending.

## Python research

Start with [Python setup](docs/SETUP.md#python-research-environment),
[framework and compatibility](docs/PYTHON_RESEARCH.md), and the
[weekly RSI study](docs/RSI_STUDY.md). Install once from the repository root;
all entry points share dependency definitions. Yahoo fetching is explicit and
cache replay supports offline feature regeneration. RSI predictor, outcome and
path tables remain separate.

```text
python -I -S tools/test_research_offline.py
```

Use the virtual-environment interpreter. These tests use synthetic data and
block Python network/subprocess access before test collection. No credentials,
provider requests, strategy optimization or Pine changes are required.

## Use an indicator

1. Open the desired `pine/*.pine` file in a UTF-8 editor and copy its complete contents.
2. In TradingView, open a chart and the Pine Editor, then create a new indicator.
3. Replace its contents, save, and select **Add to chart**.
4. Review the inputs and follow [validation](docs/VALIDATION.md).

Compilation and execution happen through TradingView. No Python, Node, Docker or
local package installation is required for the Pine indicators. Optional Python environment commands are in
[setup](docs/SETUP.md#python-research-environment). See TradingView's
[official first-indicator guide](https://www.tradingview.com/pine-script-docs/primer/first-indicator/).
Saving a TradingView copy does not update the local Git file; copy accepted edits
back to the canonical file before committing.

## Development and portability

Read [setup and private repository publication](docs/SETUP.md) for Windows
PowerShell, WSL, Ubuntu and macOS. Git attributes normalize source files to LF;
EditorConfig supplies UTF-8 defaults to compatible editors.
Optional [Identifier cleanup hooks](docs/SETUP.md#identifier-cleanup-hooks) remove
`*.Identifier` files before commits/pushes and through `git stage-clean`;
enable them once per clone.

[AGENTS.md](AGENTS.md) defines project instructions for coding agents, including
Pine changes, verification and publication boundaries. Open this repository as the
agent workspace. Codex discovers this filename as documented in the
[official OpenAI guide](https://developers.openai.com/codex/guides/agents-md).
No background agent service is installed by this repository.

See [status and next steps](docs/STATUS.md) and the [initial source manifest](docs/BASELINE.md).
The two `pine/ChatGPT_*_Project_Prompt.md` files are preserved historical prompt templates;
current project instructions live in `AGENTS.md`.

## Sharing and licensing

Initial sharing is intended for a private repository. No license has been selected
and source ownership/third-party attribution has not been established in this
setup pass. Before broader distribution, confirm rights and choose an appropriate
license; this preparation does not grant an open-source license or publish the
indicators on TradingView. Hosted CI is inactive.
