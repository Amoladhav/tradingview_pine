# Project status

Updated: 2026-09-28.

## Current phase

Repository and agent bootstrap. Four existing Pine v6 indicators and two identical
prompt templates are retained with unchanged working-file bytes. There is no
application runtime, dependency installation, order service or active hosted CI.

Prepared: standalone AGENTS instructions (including shared policy revision 7),
README/script inventory, platform and publication guide, verification checklist,
Git ignores, line-ending/editor rules and initial source provenance manifest.

## Verification

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
3. Record TradingView acceptance for all four indicators and platform smoke checks.
4. Choose a license before any public release; public publication is not authorized.
5. Make subsequent indicator changes in small commits using VALIDATION.md.

Future work, not implemented: deterministic signal fixtures or a separately
validated Python reference if needed; local automated checks; multi-OS hosted CI
only after explicit activation. Preserve one canonical Pine file per indicator.
