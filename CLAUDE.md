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

## Shared mutable state — `data/raw` is cross-repo

`data/raw/{prices,edgar}` is **one physical store, 824M, shared with the
signal-lab repo.** signal-lab's `data/raw/prices` and `data/raw/edgar` are
symlinks pointing into this checkout, so `signal-lab ingest` — run monthly
by signal-lab's `data-refresh` skill — writes through them into these
directories. `uv run split-signal ingest` writes the same store from this
side.

**One ingest or cache-writing campaign at a time**, across every worktree of
this repo *and* across signal-lab. Two concurrent writers corrupt a cache
that costs hours to rebuild against rate-limited sources.
`docs/DATA_QUALITY.md` is updated by those runs and rides the same pen.

**Pen registry: `tasks/todo.md`** — canonical for both repos. Check it
before running ingest; record it there when you take the pen.

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
