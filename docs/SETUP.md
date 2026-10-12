# Platform setup and private publication

## What is required

For editing: Git and a UTF-8 text editor. For running: TradingView's browser Pine
Editor and your own account. These Pine scripts have no local Python/Node runtime
or OS-specific binary dependencies. A coding agent is optional and is installed
and authenticated separately by the user; open this checkout as its workspace.
Ask it to summarize `AGENTS.md` to check that it loaded the project instructions.

## Native Windows (PowerShell)

Install Git for Windows from [git-scm.com](https://git-scm.com/downloads/win), then
open a new PowerShell window. Once the private remote exists, replace OWNER below
with your GitHub account or organization:

```powershell
git --version
New-Item -ItemType Directory -Force "$HOME/projects" | Out-Null
Set-Location "$HOME/projects"
git clone https://github.com/OWNER/tradingview_pine.git
Set-Location tradingview_pine
git status --short --branch
```

Open the folder in your editor. Quote paths containing spaces, especially
`"pine/630 First Candle Marker.pine"`. Use the TradingView browser workflow in README.

## WSL / Ubuntu (Bash)

Inside Ubuntu or your WSL Ubuntu distribution, install Git if needed:

```bash
sudo apt update
sudo apt install git
```

Clone inside the Linux home directory. Prefer a separate native Windows clone
if using Windows Git too; avoid switching two Git installations over one checkout.

```bash
mkdir -p "$HOME/projects"
cd "$HOME/projects"
git clone https://github.com/OWNER/tradingview_pine.git
cd tradingview_pine
git status --short --branch
```

For WSL, the browser may run on Windows while source editing happens in WSL.
WSL verification does not count as native Windows or native Ubuntu verification.

## macOS (Terminal, zsh or Bash)

Run `git --version`. If Git is unavailable, run `xcode-select --install` and finish
the system installation prompt. Then use the same clone commands as the Bash
section above. Open TradingView in the browser and use the same Pine source.

## Python research environment

Use Python 3.12 or newer. The current offline validation environment uses
Python 3.14.4; native Windows, WSL, Ubuntu and macOS acceptance remain separate.
Dependencies are defined once in `pyproject.toml`, with Yahoo, Parquet and Tradier
extras. Installation may contact the package index and run the standard packaging
backend; it does not fetch market data or resolve provider credentials.

From the repository root on WSL / Ubuntu (Bash) or macOS (zsh/Bash):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[all]'
.venv/bin/python -I -S tools/test_research_offline.py
.venv/bin/python python_scritps/rsi_weekly_study.py --help
```

Native Windows (PowerShell):

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[all]'
.\.venv\Scripts\python.exe -I -S tools/test_research_offline.py
.\.venv\Scripts\python.exe python_scritps/rsi_weekly_study.py --help
```

The virtual environment is ignored by Git. Create a separate one per OS; never
share Windows and WSL environments. For only the weekly RSI pipeline,
`python -m pip install -e '.[yahoo]'` installs its provider extra. Parquet and
Tradier commands require their respective extras. Legacy requirements files
forward to the root definition and must be invoked from the repository root.
Direct dependency pins reproduce the reviewed environment; transitive locking
and installation on each target OS remain release checks.

Installed commands: `research-rsi-weekly`, `research-directional`,
`research-adaptive`, `research-earnings`, `research-compact-csv`,
`research-range`, `research-intraday`, and `research-tradier-iv`.
Use each command's `--help` for its arguments. Existing file paths remain valid.
Yahoo collection requires an explicit `--fetch`; the default reads matching
cached captures. See [framework and migration notes](PYTHON_RESEARCH.md) and
[RSI collection/replay commands](RSI_STUDY.md).

All credentialed Tradier execution remains owner-run. Never paste a token into
commands or documentation. No automatic provider execution, scheduler or
background worker is installed.

## Keep clones consistent

- Use Git commits to synchronize accepted edits. Commit locally, then the owner
  pushes; on another clean clone run `git pull --ff-only` before editing.
- `.gitattributes` stores Pine/Markdown as LF regardless of global `core.autocrlf`.
  Existing local CRLF source bytes were preserved during setup; future checkouts
  use LF. EditorConfig-aware editors use UTF-8. Do not autoformat Pine wholesale.
- Keep filename case exact. Avoid case-only renames, Windows-reserved names and
  absolute personal paths in new code. Spaces in existing names are supported.
- Pine indicators need no virtual environment. Python scripts are in
  `python_scritps/`; use a separate environment on each OS. Python dependencies and commands
  are centralized in `pyproject.toml`; per-platform execution remains pending.
- Match symbol/exchange, chart interval, session, adjustment settings, inputs and
  history when comparing charts. The candle marker's current default is 06:30
  America/Los_Angeles; it is an explicit script input, not the computer timezone.

## Identifier cleanup hooks

The versioned `.githooks/` scripts delete literal, case-sensitive `*.Identifier`
files throughout this working tree before commits and pushes. Ignored directories
are included; `.git`, nested repositories/submodules and symlink targets are not
traversed. Matching symlinks themselves are removed; directories are not deleted.
This does not remove Windows alternate data streams such as `:Zone.Identifier`.
The existing `.gitignore` rule also excludes these files from ordinary staging.

Enable once in each clone, using PowerShell, Bash or zsh:

```text
git config --local core.hooksPath .githooks
git config --local alias.stage-clean "!sh .githooks/stage_clean.sh"
```

Review any existing hooks before replacing `core.hooksPath`. Git does not install
this configuration when cloning. Git for Windows supplies the shell and utilities;
no Python dependency is needed for the hooks. Native Windows, WSL, native Ubuntu
and macOS acceptance remain separate pending checks.

Git has no pre-staging hook. Use `git stage-clean .` or `git stage-clean --all`
instead of `git add` when cleanup is wanted at staging time. Path arguments retain
the caller's directory context. Ordinary `git add` and GUI staging do not invoke
cleanup; the commit hook is the fallback.

If matching files are already staged or tracked, the commit hook deletes their
working copies and stops the commit. Review and stage their removals explicitly
(or use `git stage-clean --all` after reviewing all other changes), then retry.
The push hook only cleans working files: it does not alter the index, remove files
from existing commits or rewrite history. These hooks are convenience cleanup,
not a guarantee that pushed history contains no matching files. `--no-verify`
bypasses the commit/push hooks. Cleanup errors fail the triggering operation.

Offline synthetic verification (Python 3.10+ for tests only):

```text
python -I -S tools/test_identifier_hooks.py
```

Use `python3` on Linux/macOS or `py -3` on Windows if appropriate. Tests use temporary
repositories and sanitized subprocess environments with Git transports disabled;
they do not push or execute application/provider scripts.

## Publish the prepared repository (owner-run)

First review `git status`, `git log --oneline` and the source/license provenance.
The initial local commit is a source baseline, not proof of compiled indicators.
Create an **empty private** GitHub repository named `tradingview_pine` in the web
interface, without an auto-generated README, license or gitignore. Then, from this
project folder, run the following in PowerShell, Bash or zsh after replacing OWNER:

```text
git remote add origin https://github.com/OWNER/tradingview_pine.git
git remote -v
git push -u origin main
```

Use your normal Git authentication flow; never paste credentials into a remote
URL or this repository. If origin already exists, inspect it before changing it.
These commands are for the owner; agents never push under the project policy.
Creating a remote requires separate authorization. Public sharing and hosted CI need
separate decisions. See [status](STATUS.md) for remaining acceptance checks.
