#!/usr/bin/env bash
#
# new-worktree.sh — create a worktree for a parallel workstream, wired for
# this project's gitignored local state.
#
# Usage: scripts/new-worktree.sh <branch> [dir]
#   branch  workstream branch (created from main if it does not exist)
#   dir     defaults to ../split-signal-<branch>
#
# What a bare `git worktree add` misses here, and how this handles it:
#
#   data/raw/       SYMLINKED back to the main checkout — shared, one
#                   physical store (824M of prices + EDGAR). Re-downloading
#                   is hours against rate-limited sources, so it is never
#                   copied. See the pen rule below before writing it.
#   data/processed/ NOT shared. Created empty; rebuild it in the worktree
#                   (notebooks/09_likelihood_model.py, then 10_validation.py).
#                   Deliberate: panels are regenerable, and two worktrees
#                   rebuilding through one shared dir would silently
#                   overwrite each other's parquets. A rebuild you can see
#                   beats corruption you cannot.
#   data/fixtures/  committed — travels with the checkout, nothing to wire.
#   .venv/          never copied; `uv sync` recreates it from uv.lock.
#   no .env         this repo has no secrets file, so nothing is copied.
#
# SHARED-STATE RULE — who holds the pen on data/raw:
#   data/raw is written by `uv run split-signal ingest` in THIS repo, and
#   ALSO by signal-lab: its data/raw/{prices,edgar} are symlinks into this
#   checkout, so `signal-lab ingest` (run monthly by signal-lab's
#   data-refresh skill) writes through them into these same directories.
#   Only ONE ingest or cache-writing campaign may run at a time — across
#   every worktree of this repo AND across signal-lab. docs/DATA_QUALITY.md
#   is updated by those runs and rides the same pen.
#   Pen registry: tasks/todo.md (canonical for both repos).

set -euo pipefail

MAIN="$(git rev-parse --show-toplevel)"
BRANCH="${1:?usage: scripts/new-worktree.sh <branch> [dir]}"
DIR="${2:-$MAIN/../split-signal-$BRANCH}"

if git -C "$MAIN" show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git -C "$MAIN" worktree add "$DIR" "$BRANCH"
else
  git -C "$MAIN" worktree add -b "$BRANCH" "$DIR" main
fi

DIR="$(cd "$DIR" && pwd)"

mkdir -p "$DIR/data"
ln -sfn "$MAIN/data/raw" "$DIR/data/raw"
mkdir -p "$DIR/data/processed"

echo
echo "worktree ready: $DIR (branch: $BRANCH)"
echo
echo "  data/raw       -> SHARED symlink into the main checkout."
echo "                    signal-lab writes this store too — one ingest at a"
echo "                    time, across both repos. Pen: tasks/todo.md."
echo "  data/processed -> empty and yours; rebuild with"
echo "                    uv run python notebooks/09_likelihood_model.py"
echo "                    uv run python notebooks/10_validation.py"
echo
echo "  next: cd $DIR && uv sync && uv run pytest"
