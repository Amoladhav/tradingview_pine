# Project status

Updated: 2026-10-10.

## Current phase

Folder-layout documentation aligned with the owner's restructuring: ten canonical
Pine indicators and two prompt templates now reside in `pine/`. Python source is
in `python_scritps/` (spelling preserved), with `directional_range_study.py` present.
The root `universe.csv` is unreviewed local data. Python dependencies, supported
versions, I/O behavior and runtime acceptance remain pending.

AGENTS, README, setup, validation and baseline path notes now reflect this layout.
The moved Pine/template contents match HEAD after LF normalization. The templates
differ; their added Style-tab and numerical alert-output guidance is reconciled in
AGENTS, preserving existing filenames and truthful static-review reporting.
No source edits, revision
increments, calculations, displays, settings, alerts or timeframe changes were
made by this documentation update. Owner source moves and new Python/data files
remain outside the documentation commit.

Documentation checks: UTF-8, relative links, inventory consistency, shared-policy
preservation, Git whitespace review and value-suppressing staged scan. No Python
script execution or Pine compile-safety pass was performed. TradingView compilation,
chart/alert acceptance and native Windows, WSL, Ubuntu and macOS checks remain pending.

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

Future work, not implemented: deterministic signal fixtures or a separately
validated Python reference if needed (the present research script is not yet
validated); local automated checks; multi-OS hosted CI only after explicit activation. Preserve one canonical Pine file per indicator.
