# Wiki Conventions

How the wiki is maintained consistently. Living document — may grow.

## File names

- Lowercase, hyphens instead of spaces
- Category prefix optional when the slug is unambiguous
- Examples: `harald-innkeeper.md`, `oakford.md`, `sword-of-forgetting.md`

## IDs

Schema: `<type>-<slug>` — e.g. `npc-harald-innkeeper`, `loc-oakford`, `item-sword-of-forgetting`. Must be globally unique.

## Tags — controlled list

When a new tag becomes useful, add it here instead of inventing it ad hoc.

**Status:** `alive`, `dead`, `unknown`, `missing`, `active`, `resolved`, `dormant`
**Disposition (NPCs):** `allied`, `friendly`, `neutral`, `wary`, `hostile`, `unknown`
**Importance:** `major`, `minor`, `seed`
**Location type:** `village`, `town`, `city`, `ruin`, `dungeon`, `wilderness`, `harbor`, `island`
**Thematic:** `memory`, `character-past`, `mystical`, `political`

_Add categories/values as the campaign requires. Keep the list curated — don't let synonyms multiply._

## Importance levels

- **major:** central to the main plot, full article
- **minor:** recurring relevance, Quick Reference is usually enough
- **seed:** pre-planted, not yet activated, details only when triggered

## Linking

Obsidian-style: `[[npc-harald-innkeeper]]` or `[[npc-harald-innkeeper|Harald]]` when an alternative display text is needed.

## Index maintenance

Each category has an `_index.md`. One-liner per entry, format:

`- [[id]] — <summary from frontmatter>. [tags]`

Grouping by region or theme is allowed.

## Session logs

`sessions/YYYY-MM-DD-NN.md` — `NN` = sequence number per day (`01`, `02`, …).
Minimal frontmatter: `date`, `duration_minutes` (optional), `summary`.

## Git mode conventions

See `meta/git-protocol.md` for the rules these names serve.

**Branches:**

- `action/<slug>` — a player action PR branch
- `gm/turn-<N>-pr<num>` — a GM turn PR branch (created by the GM workflow)
- `timeline/<slug>` — an alternate timeline being played
- `archive/timeline/<slug>` — a **tag** preserving an abandoned timeline
- `demo-campaign` — the ready-to-play example setting

**Labels:** `player-action`, `gm-turn`, `session-zero`, `timeline-merge`, `paradox`,
`quest:active`, `quest:resolved`, `quest:failed`, `seed`.

**Rolls block** (in action PR bodies): a fenced ` ```rolls ` block, one roll per line —
`<action-id>: NdS[+M|-M]  # optional purpose`, with `action-id` matching
`[a-z0-9-]{1,40}` and unique within the PR.
