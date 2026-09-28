Treat this Pine Script as a Git-managed source file.

## Source-of-truth rules

1. The supplied `.pine` file is the current source of truth.
2. Keep the same canonical filename unless I explicitly request a rename.
3. Do NOT create filenames such as `_v2`, `_v3`, `_final`, `_fixed`, etc.
4. Git history, not filenames, will track versions.
5. Never reconstruct older portions of the script from memory when the current source is available.
6. Preserve existing behavior unless the requested change explicitly modifies it.

## For every iteration

Make only the requested changes and avoid unrelated refactoring.

Before modifying code:

* identify the affected logic;
* distinguish calculation changes from display-only changes;
* identify any impact on alerts, timeframe behavior, plots, settings, or historical behavior.

For Pine Script:

* perform the full compile-safety/static syntax pass required by this project;
* prefer explicit compiler-safe Pine syntax over compact syntax;
* do not introduce multiline chained ternaries or fragile multiline statements;
* preserve working `request.security()` and timeframe behavior unless specifically changing them;
* do not silently change repaint/lookahead behavior.

## Alerts

Do not rename, remove, combine, or add alerts without calling it out.

If a new alert is required, propose the exact alert name and meaning for my validation before treating the implementation as final.

Existing alert names and conditions should remain unchanged unless explicitly requested.

## Settings

Preserve:

* existing inputs and defaults;
* show/hide controls;
* line/text formatting controls;
* timeframe controls;
* frozen-timeframe behavior.

If the requested feature cannot function correctly with a frozen timeframe, explicitly state that.

Tooltips/pop-up comments should remain concise but sufficiently descriptive to make the correct setting choice.

## Deliverables after each change

Return:

1. **Full updated `.pine` file** using the canonical filename.

2. **Change summary** — only what changed.

3. **Behavior impact** — calculation / display / alert / timeframe.

4. **Git commit message** in this format:

   `type(scope): concise description`

   Prefer:

   * `feat` for new functionality
   * `fix` for a correction
   * `refactor` for structural change without behavior change
   * `style` for display-only changes
   * `docs` for documentation/comments
   * `chore` for maintenance

5. **Suggested Git diff summary**, for example:
   `2 files changed, 14 insertions(+), 3 deletions(-)`

6. Mention whether TradingView compilation was actually performed. If TradingView's compiler is unavailable, state:
   `Static Pine compile-safety pass completed; TradingView compiler not available in this environment.`

## Versioning

Do not put iteration numbers in the filename.

If an internal script version is useful, maintain it in a short header comment such as:

`// Revision: 1.12`

Only increment that revision when code is actually changed.

## Current requested change

[Describe the requested change here.]

Make the smallest safe change necessary.
