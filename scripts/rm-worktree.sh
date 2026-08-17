#!/usr/bin/env bash
#
# rm-worktree.sh — tear down a finished workstream worktree; the mirror of
# new-worktree.sh.
#
# Usage: scripts/rm-worktree.sh <branch> [--force] [--delete-remote]
#   branch           workstream branch whose worktree should be removed
#   --force          also accept a branch git cannot see as merged (needed
#                    after a squash-merge, where the branch tip never
#                    becomes an ancestor of main)
#   --delete-remote  also delete origin/<branch> after local teardown
#
# Safety gates, all of which must pass, in order:
#   1. the branch has a registered worktree whose directory still exists,
#      and it is not the main checkout
#   2. you are not standing inside the worktree being removed
#   3. the worktree is clean (ignored files do not count and go with it)
#   4. the branch is merged into main, locally or on origin (skipped with
#      --force)
#
# What removal destroys: the worktree directory, including its .venv and its
# rebuilt data/processed. The data/raw SYMLINK is removed but its TARGET —
# the shared 824M cache in the main checkout, which signal-lab also reads —
# is never touched.
#
# ORDER MATTERS, AND SO DOES WHO DECIDES. The worktree has to be removed
# before the branch, because git will not delete a branch that is still
# checked out — which makes the removal irreversible by the time the branch
# delete runs. So nothing after it may veto: gate 4 above is the sole
# authority and the branch goes with `git branch -D`. `git branch -d` asks a
# DIFFERENT question — reachable from HEAD or upstream, not "merged into
# main" — and when the two disagree it refuses with the worktree already
# gone, leaving a half-torn-down repo, no prune, and an error that steers
# the next attempt to --force, the one flag that skips the merged gate.

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

# A registered worktree whose directory is gone is 'prunable', and every gate
# below would pass vacuously on it. Stop rather than delete the branch of a
# checkout that may only have been moved.
if [ ! -d "$DIR" ]; then
  echo "refusing: '$BRANCH' is registered at $DIR but that directory does not exist." >&2
  echo "  If the worktree was moved: git -C $MAIN worktree repair" >&2
  echo "  If it is really gone:      git -C $MAIN worktree prune" >&2
  exit 1
fi

# 2. do not saw off the branch you are sitting on
case "$PWD/" in
  "$DIR"/*) echo "refusing: current directory is inside $DIR — cd out first (e.g. to $MAIN)" >&2; exit 1 ;;
esac

# 3. clean check — capture the output and the EXIT CODE separately. A command
#    substitution inside [ -n ... ] throws the exit code away, so a git status
#    that FAILS produces empty output and reads as "clean".
if ! STATUS="$(git -C "$DIR" status --porcelain 2>&1)"; then
  echo "refusing: cannot read the status of the worktree at $DIR:" >&2
  printf '%s\n' "$STATUS" >&2
  exit 1
fi
if [ -n "$STATUS" ]; then
  echo "refusing: worktree at $DIR has uncommitted or untracked changes:" >&2
  git -C "$DIR" status --short >&2
  exit 1
fi

# 4. merged check. Fully-qualified refs only: a bare name lets a same-named
#    TAG win the lookup and make an unmerged branch look merged. Check origin
#    as well as local main — workstreams here merge by PR on GitHub, so local
#    main is routinely behind and a local-only test would report a merged
#    branch as unmerged, training the --force habit.
MERGED=0
git -C "$MAIN" fetch --quiet origin main 2>/dev/null || true
for base in refs/heads/main refs/remotes/origin/main; do
  git -C "$MAIN" show-ref --verify --quiet "$base" || continue
  if git -C "$MAIN" merge-base --is-ancestor "refs/heads/$BRANCH" "$base"; then
    MERGED=1
    break
  fi
done
if [ "$MERGED" -ne 1 ] && [ "$FORCE" -ne 1 ]; then
  echo "refusing: '$BRANCH' is not merged into main (local or origin)." >&2
  echo "  If its PR was squash-merged (the branch tip never lands in main)," >&2
  echo "  verify the PR is merged, then re-run with --force." >&2
  exit 1
fi

git -C "$MAIN" worktree remove "$DIR"
# -D, not -d: see the header. Gate 4 above is the authority, and nothing may
# veto once the worktree — the irreversible part — is already gone.
git -C "$MAIN" branch -D "$BRANCH"
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
