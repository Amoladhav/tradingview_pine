#!/bin/sh
# Delete only literal, case-sensitive *.Identifier files; never read contents.
set -eu
repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

# find does not follow symlinks. Prune Git metadata and nested repositories,
# including submodules/worktrees whose .git is a file.
find . \( -name .git -o \( -type d ! -path . -exec test -e '{}/.git' \; \) \) -prune -o \
    \( -type f -o -type l \) -name '*.Identifier' -exec rm -f -- {} +
