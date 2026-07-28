# CLAUDE.md — split-signal

Research on whether stock splits carry a tradeable signal. Findings live in
`docs/METHODOLOGY.md` and `docs/research/`; data provenance and known gaps
in `docs/DATA_QUALITY.md`. Current state: `tasks/todo.md`.

This is a **research tool, not investment advice** — that framing is in the
README and applies to anything generated here.

## Commands

Python ≥3.11, uv-managed. Both of these must be green before any commit
(CI runs the same pair on PRs and pushes to main):

```
uv sync                # install from uv.lock
uv run ruff check .    # lint
uv run pytest          # 100 tests, no network — fixtures only
```

Rebuilding derived data (not part of the commit bar):

```
uv run python notebooks/09_likelihood_model.py   # retrain, rebuilds panel
uv run python notebooks/10_validation.py         # re-validate
```

## Shared mutable state — `data/raw`

`data/raw/{prices,edgar}` is **one physical store, 824M**, written only by
`uv run split-signal ingest`. Every worktree symlinks to the same directory,
so writes from any of them land in the same place.

**One ingest or cache-writing campaign at a time**, across every worktree of
this repo. Two concurrent writers corrupt a cache that costs hours to
rebuild against rate-limited sources. `docs/DATA_QUALITY.md` is updated by
those runs and rides the same pen.

**Pen registry: `tasks/todo.md`.** Check it before running ingest; record it
there when you take the pen.

**signal-lab reads this cache but never writes it.** Its
`data/raw/{prices,edgar}` are symlinks into this checkout; its own ingest
writes only to its `*_local` overlay directories, enforced structurally by
`signal_lab.data.cache.write_path` (decision D1 in signal-lab's
`tasks/plan.md`). So signal-lab is not a co-holder of the pen — but
deleting, relocating, or rewriting `data/raw` here breaks it silently.
Ordinary ingest top-ups are safe for it; destructive changes need
coordination.

`data/processed` is deliberately NOT shared between worktrees — it is
regenerable, and concurrent rebuilds through one directory would silently
overwrite each other. Rebuild it per worktree.

## Parallel workstreams (worktrees)

One branch per workstream, one worktree per branch, created via
`scripts/new-worktree.sh <branch>` and torn down via
`scripts/rm-worktree.sh` (or the repo's `worktree-cleanup` skill). The
script wires the `data/raw` symlink and leaves `data/processed` empty for
you to rebuild.

`main` is the review inbox: workstreams merge back via PRs, never by
committing directly to main alongside another session.

## Commits and PRs

- Tests and lint green before **every** commit, not just before the PR.
- Faithful commit messages describing why; no attribution trailers.
- PRs are decisions-first (see the PR template) and are opened for owner
  review — never merged by Claude.
- ⛳ Ask first: any paid data source or non-trivial spend, adding a heavy
  dependency, and anything that changes methodology in a way that would
  alter a published finding.
