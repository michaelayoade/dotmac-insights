# Migration Policy

## Goals
- Keep a single Alembic head outside release windows.
- Avoid merge-of-merge chains.
- Make the migration graph easy to reason about.

## Workflow
1. Rebase onto the latest head before creating a migration.
2. Generate migrations from the current head only.
3. If multiple heads appear, merge them once and continue from that merge.

## Release Merge
- Create a single merge revision that references all active heads.
- Point all subsequent migrations at that merge.
- Avoid creating a second merge that depends on another merge.

## Checks
- Run `make db-head-check` before merging a branch.
- CI should fail if more than one head exists unless explicitly allowed.
