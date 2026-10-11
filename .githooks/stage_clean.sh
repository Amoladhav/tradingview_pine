#!/bin/sh
set -eu
repo_root=$(git rev-parse --show-toplevel)
sh "$repo_root/.githooks/clean_identifiers.sh"
# Git shell aliases run from the root; restore the caller's pathspec context.
cd "$repo_root/${GIT_PREFIX:-}"
exec git add "$@"
