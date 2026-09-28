# TradingView Pine indicators

Four standalone Pine Script v6 indicators, maintained as canonical source files
with Git history. This repository contains indicators, not an order execution
service or a locally runnable trading application.

| Source | Purpose |
| --- | --- |
| [630 First Candle Marker.pine](630%20First%20Candle%20Marker.pine) | Mark a configurable intraday candle time. |
| [CCIEMA_percentile_extremes.pine](CCIEMA_percentile_extremes.pine) | CCI, EMA signal and adaptive percentile extremes. |
| [Volume_Outlier_Profile.pine](Volume_Outlier_Profile.pine) | Comparable-volume percentile, relative volume and robust outlier display. |
| [Price_Response_To_Colume.pine](Price_Response_To_Colume.pine) | Price range/body response relative to comparable volume. |

Descriptions summarize the source; numerical and TradingView validation remain
pending. The existing filename spelling is intentional for source continuity.

## Use an indicator

1. Open the desired `.pine` file in a UTF-8 editor and copy its complete contents.
2. In TradingView, open a chart and the Pine Editor, then create a new indicator.
3. Replace its contents, save, and select **Add to chart**.
4. Review the inputs and follow [validation](docs/VALIDATION.md).

Compilation and execution happen through TradingView. No Python, Node, Docker or
local package installation is required for these scripts. See TradingView's
[official first-indicator guide](https://www.tradingview.com/pine-script-docs/primer/first-indicator/).
Saving a TradingView copy does not update the local Git file; copy accepted edits
back to the canonical file before committing.

## Development and portability

Read [setup and private repository publication](docs/SETUP.md) for Windows
PowerShell, WSL, Ubuntu and macOS. Git attributes normalize source files to LF;
EditorConfig supplies UTF-8 defaults to compatible editors.

[AGENTS.md](AGENTS.md) defines project instructions for coding agents, including
Pine changes, verification and publication boundaries. Open this repository as the
agent workspace. Codex discovers this filename as documented in the
[official OpenAI guide](https://developers.openai.com/codex/guides/agents-md).
No background agent service is installed by this repository.

See [status and next steps](docs/STATUS.md) and the [initial source manifest](docs/BASELINE.md).
The two `ChatGPT_*_Project_Prompt.md` files are preserved historical prompt templates;
current project instructions live in `AGENTS.md`.

## Sharing and licensing

Initial sharing is intended for a private repository. No license has been selected
and source ownership/third-party attribution has not been established in this
setup pass. Before broader distribution, confirm rights and choose an appropriate
license; this preparation does not grant an open-source license or publish the
indicators on TradingView. Hosted CI is inactive.
