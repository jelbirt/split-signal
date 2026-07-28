---
name: worktree-cleanup
description: Tear down finished git worktrees safely - verify each branch is merged and its tree is clean, then remove the worktree, delete the branch, and prune. Sweeps every merged-and-clean worktree at once, or targets one branch. Use when the user wants to clean up, tear down, close out, or remove a worktree or workstream, says "worktree cleanup", "sweep merged worktrees", "remove finished worktrees", or asks to delete a finished branch's directory. Delegates to scripts/rm-worktree.sh, which owns the safety gates.
argument-hint: [branch, or "sweep" to find all merged worktrees; defaults to sweep]
model: sonnet
---

# worktree-cleanup

Close out finished workstreams: remove the worktree directory, delete the
local branch, and prune worktree metadata — only for branches that are
merged and trees that are clean. Decide *what* to tear down, confirm with
the user, then do it via `scripts/rm-worktree.sh`, which owns the gates.

## Instructions

1. **Orient.** Work from the main checkout. The default branch is `main`,
   and every removal goes through `scripts/rm-worktree.sh`.

2. **Resolve targets.** If `$ARGUMENTS` names a branch, that is the only
   candidate. Otherwise (or on "sweep"), walk `git worktree list --porcelain`
   and skip entries with no `branch` line (detached HEAD or bare) plus the
   main checkout itself. For each remaining worktree, check both:
   - **Merged** — `git merge-base --is-ancestor {branch} main`, falling
     back to `gh pr list --state merged --head {branch}` to catch
     squash-merges, which the ancestor check cannot see.
   - **Clean** — `git -C {dir} status --porcelain` is empty.

3. **Present the plan and get confirmation.** List candidates with branch,
   directory, and merge evidence (ancestor vs merged PR number); then list
   every worktree SKIPPED with the reason — unmerged, dirty, or it is the
   worktree this session is running in. Git refuses to remove the directory
   you are standing in; hand that one to a session in another checkout or
   run from the main checkout.

   In this repo the untracked casualties are the worktree's `.venv`
   (recreated by `uv sync`) and its rebuilt `data/processed` (regenerated
   by `notebooks/09_likelihood_model.py` then `10_validation.py`) — say so,
   since a long rebuild is worth knowing about before it is discarded.
   `data/raw` is a SYMLINK into the main checkout; removal deletes the link
   only, and the shared 824M cache — which signal-lab also reads through its
   own symlinks — is never at risk. Never remove anything before the user
   confirms.

4. **Tear down each confirmed branch** from the main checkout:
   `scripts/rm-worktree.sh {branch}`. Add `--force` only for a squash-merge
   you verified via PR state in step 2, and `--delete-remote` only if the
   user asked — GitHub's "delete branch after merge" setting usually
   handled it already.

5. **Report.** What was removed, what remains (`git worktree list`), and
   every candidate skipped or refused by a gate.

## Notes

- Never tear down the main checkout, and never delete a branch that is not
  merged — flag unmerged or dirty workstreams for the user instead.
- A failing gate is information, not an obstacle. Report it; do not work
  around it with `--force`, `-D`, or `rm -rf` unless the user explicitly
  asks after seeing the reason.
