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
#   data/raw is written only by `uv run split-signal ingest`, and every
#   worktree symlinks to the same physical directory. Only ONE ingest or
#   cache-writing campaign may run at a time across all of them.
#   docs/DATA_QUALITY.md is updated by those runs and rides the same pen.
#   Pen registry: tasks/todo.md.
#
#   signal-lab READS this cache (its data/raw/{prices,edgar} are symlinks
#   into this checkout) but never writes it — its ingest writes only to its
#   own *_local overlay dirs. It is not a pen co-holder, but deleting or
#   relocating data/raw here breaks it silently.

set -euo pipefail

MAIN="$(git rev-parse --show-toplevel)"
BRANCH="${1:?usage: scripts/new-worktree.sh <branch> [dir]}"
DIR="${2:-$(dirname "$MAIN")/$(basename "$MAIN")-$BRANCH}"

# A half-finished worktree is worse than none: it can look ready while
# missing its data wiring, or leave a branch behind with no worktree. Undo
# whatever we created if any step below fails.
BRANCH_PREEXISTED=0
git -C "$MAIN" show-ref --verify --quiet "refs/heads/$BRANCH" && BRANCH_PREEXISTED=1

cleanup_failed() {
  echo "new-worktree.sh: failed — rolling back" >&2
  git -C "$MAIN" worktree remove --force "$DIR" 2>/dev/null || true
  if [ "$BRANCH_PREEXISTED" -eq 0 ]; then
    git -C "$MAIN" branch -D "$BRANCH" 2>/dev/null || true
  fi
  git -C "$MAIN" worktree prune 2>/dev/null || true
}
trap cleanup_failed ERR

if [ "$BRANCH_PREEXISTED" -eq 1 ]; then
  git -C "$MAIN" worktree add "$DIR" "$BRANCH"
else
  git -C "$MAIN" worktree add -b "$BRANCH" "$DIR" main
fi

DIR="$(cd "$DIR" && pwd)"

mkdir -p "$DIR/data"
ln -sfn "$MAIN/data/raw" "$DIR/data/raw"
mkdir -p "$DIR/data/processed"

trap - ERR

echo
echo "worktree ready: $DIR (branch: $BRANCH)"
echo
echo "  data/raw       -> SHARED symlink into the main checkout."
echo "                    One ingest at a time across all worktrees."
echo "                    Pen: tasks/todo.md."
echo "  data/processed -> empty and yours; rebuild with"
echo "                    uv run python notebooks/09_likelihood_model.py"
echo "                    uv run python notebooks/10_validation.py"
echo
echo "  next: cd $DIR && uv sync && uv run pytest"
