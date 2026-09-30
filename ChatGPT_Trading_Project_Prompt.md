# Pine Script Development Rules

Treat every Pine Script as a **Git-managed source file**. Make the smallest safe change necessary and preserve existing behavior unless the request explicitly changes it.

## Source of Truth

* The supplied `.pine` file is always the current source of truth.
* Never reconstruct existing code from memory when the source file is available.
* Preserve the canonical filename unless I explicitly request a rename.
* Replace spaces in filenames with `_`.
* Never create versioned filenames such as `_v2`, `_final`, `_fixed`, etc. Git tracks versions.
* If the script contains an internal revision comment such as `// Revision: 1.12`, increment it only when code changes.

## Before Editing

Identify:

* affected logic;
* whether the change is **calculation**, **display**, **alert**, **settings**, or **timeframe** related;
* any effect on historical behavior, repaint/lookahead behavior, alerts, plots, inputs, or frozen-timeframe behavior.

Do not perform unrelated refactoring.

## Pine Safety

* Perform a full static Pine compile-safety/syntax review.
* Prefer explicit, compiler-safe syntax.
* Avoid fragile multiline expressions and multiline chained ternaries.
* Preserve working `request.security()` logic and timeframe behavior unless specifically requested.
* Never silently alter repaint, confirmation, or lookahead behavior.

## Alerts

Existing alerts are part of the script contract.

* Do not rename, remove, combine, or alter existing alert conditions unless explicitly requested.
* Do not add alerts silently.
* If a new alert is needed, state its **exact proposed name and meaning** for validation before treating it as final.
* Preserve numerical alert outputs needed for TradingView user-defined thresholds.

## Settings & Timeframes

Preserve existing:

* inputs and defaults;
* show/hide controls;
* formatting controls;
* colors, widths, styles, and text controls;
* timeframe controls;
* frozen-timeframe behavior.

If a requested feature cannot work correctly with a frozen timeframe, explicitly state that.

Tooltips should be concise but sufficient for choosing the correct setting.

## Style-Tab Hygiene

Expose only controls with meaningful visible effects.

Classify every plot/shape/line/background as:

1. **User-visible**
2. **Optional visible**
3. **Internal/output-only**

Only the first two should normally expose Style controls.

For plots used only for alerts, calculations, screeners, Data Window values, or plumbing:

* use `editable=false` where supported;
* use `display` independently to control where the value appears.

Remember: `display` controls visibility/location; `editable` controls Style-tab customization.

Do not remove useful Inputs merely to reduce clutter. If appearance is already intentionally controlled through Inputs, suppress redundant automatic Style controls where appropriate.

## Change Discipline

For every iteration:

* modify only what was requested;
* preserve unrelated calculations and behavior;
* preserve existing alerts and settings;
* preserve timeframe semantics;
* preserve historical/repaint behavior unless explicitly changing it.

## Required Deliverables

After every code change, return:

1. **Full updated `.pine` file** using the canonical filename.
2. **Change summary** — only what changed.
3. **Behavior impact** covering:

   * Calculation
   * Display
   * Alerts
   * Timeframe
4. **Git commit message**:

   `type(scope): concise description`

   Preferred types:

   * `feat` — new functionality
   * `fix` — correction
   * `refactor` — structural change without behavior change
   * `style` — display-only change
   * `docs` — comments/documentation
   * `chore` — maintenance
5. **Suggested Git diff summary**, e.g.
   `1 file changed, 14 insertions(+), 3 deletions(-)`
6. Compilation status.

If TradingView's actual compiler was not used, state exactly:

`Static Pine compile-safety pass completed; TradingView compiler not available in this environment.`

## Default Principle

**Preserve behavior, minimize the diff, keep the UI meaningful, and make every modification auditable through Git.**
