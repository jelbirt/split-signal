#!/usr/bin/env bash
#
# rm-worktree.sh — tear down a finished workstream worktree; the mirror of
# new-worktree.sh.
#
# Usage: scripts/rm-worktree.sh <branch> [--force] [--delete-remote]
#   branch           workstream branch whose worktree should be removed
#   --force          skip the merged-into-main check and force-delete the
#                    branch (needed after a squash-merge, where the branch
#                    tip never becomes an ancestor of main)
#   --delete-remote  also delete origin/<branch> after local teardown
#
# Safety gates, all of which must pass, in order:
#   1. the branch has a registered worktree, and it is not the main checkout
#   2. you are not standing inside the worktree being removed
#   3. the worktree is clean (ignored files do not count and go with it)
#   4. the branch is merged into main (skipped with --force)
#
# What removal destroys: the worktree directory, including its .venv and its
# rebuilt data/processed. The data/raw SYMLINK is removed but its TARGET —
# the shared 824M cache in the main checkout, which signal-lab also reads —
# is never touched.

set -euo pipefail

BRANCH=""
DELETE_REMOTE=0
FORCE=0

for arg in "$@"; do
  case "$arg" in
    --delete-remote) DELETE_REMOTE=1 ;;
    --force)         FORCE=1 ;;
    -*) echo "unknown flag: $arg" >&2; exit 2 ;;
    *)  [ -z "$BRANCH" ] || { echo "unexpected extra argument: $arg" >&2; exit 2; }
        BRANCH="$arg" ;;
  esac
done

[ -n "$BRANCH" ] || { echo "usage: scripts/rm-worktree.sh <branch> [--force] [--delete-remote]" >&2; exit 2; }

MAIN="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"

# 1. locate the worktree registered for this branch
DIR="$(git -C "$MAIN" worktree list --porcelain | awk -v ref="refs/heads/$BRANCH" '
  /^worktree / { dir = substr($0, 10) }
  /^branch / && $2 == ref { print dir; exit }
')"
[ -n "$DIR" ] || { echo "no worktree found for branch '$BRANCH'" >&2; exit 1; }
[ "$DIR" != "$MAIN" ] || { echo "refusing: '$BRANCH' is checked out in the main checkout, not a worktree" >&2; exit 1; }

# 2. do not saw off the branch you are sitting on
case "$PWD/" in
  "$DIR"/*) echo "refusing: current directory is inside $DIR — cd out first (e.g. to $MAIN)" >&2; exit 1 ;;
esac

# 3. clean check
if [ -n "$(git -C "$DIR" status --porcelain)" ]; then
  echo "refusing: worktree at $DIR has uncommitted or untracked changes:" >&2
  git -C "$DIR" status --short >&2
  exit 1
fi

# 4. merged check
if [ "$FORCE" -ne 1 ] && ! git -C "$MAIN" merge-base --is-ancestor "$BRANCH" main; then
  echo "refusing: '$BRANCH' is not merged into main." >&2
  echo "  If the PR merged on GitHub but local main is behind, update it" >&2
  echo "  first: git -C $MAIN pull --ff-only" >&2
  echo "  If its PR was squash-merged (the branch tip never lands in main)," >&2
  echo "  verify the PR is merged, then re-run with --force." >&2
  exit 1
fi

git -C "$MAIN" worktree remove "$DIR"
if [ "$FORCE" -eq 1 ]; then
  git -C "$MAIN" branch -D "$BRANCH"
else
  git -C "$MAIN" branch -d "$BRANCH"
fi
git -C "$MAIN" worktree prune

if [ "$DELETE_REMOTE" -eq 1 ]; then
  if git -C "$MAIN" ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
    git -C "$MAIN" push origin --delete "$BRANCH"
  else
    echo "origin/$BRANCH already gone — nothing to delete remotely"
  fi
fi

echo
echo "worktree torn down: $DIR (branch: $BRANCH)"
echo "  remaining worktrees:"
git -C "$MAIN" worktree list | sed 's/^/    /'
