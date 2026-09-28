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
`"630 First Candle Marker.pine"`. Use the TradingView browser workflow in README.

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

## Keep clones consistent

- Use Git commits to synchronize accepted edits. Commit locally, then the owner
  pushes; on another clean clone run `git pull --ff-only` before editing.
- `.gitattributes` stores Pine/Markdown as LF regardless of global `core.autocrlf`.
  Existing local CRLF source bytes were preserved during setup; future checkouts
  use LF. EditorConfig-aware editors use UTF-8. Do not autoformat Pine wholesale.
- Keep filename case exact. Avoid case-only renames, Windows-reserved names and
  absolute personal paths in new code. Spaces in existing names are supported.
- No virtual environment is needed. If Python tooling is introduced later, create
  a separate environment on each OS and document its supported versions.
- Match symbol/exchange, chart interval, session, adjustment settings, inputs and
  history when comparing charts. The candle marker's current default is 06:30
  America/Los_Angeles; it is an explicit script input, not the computer timezone.

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
