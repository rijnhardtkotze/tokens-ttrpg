# Lint Protocol

Self-improvement of the wiki. On player request via `/lint`, or offered automatically every ~5 sessions.

## Checks

1. **Orphans:** articles with no incoming links. Are they orphaned? Integrate or archive.
2. **Stale:** `last_seen` more than 10 sessions ago AND `status: alive`. Still current?
3. **Missing:** named entities mentioned in session logs that have no article of their own.
4. **Contradictions:** claims that contradict each other across articles.
5. **Index drift:** `_index.md` one-liner no longer matches the article's `summary`.
6. **Tag chaos:** synonymous tags, typos, casing inconsistencies.
7. **Tier-2 bloat:** Quick Reference longer than 10 lines → condense.
8. **Seed aging:** seeds in `meta/seeds.md` that have not been activated in 10+ sessions. Rescue or discard.

## Output

Write the result to `meta/lint-report-YYYY-MM-DD.md`. Discuss suggestions with the player, then execute.

## What is never changed automatically

- An NPC's status (alive/dead)
- Established canon in `meta/canon.md`
- Session logs (immutable)
