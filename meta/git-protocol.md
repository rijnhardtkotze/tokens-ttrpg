# The Git Protocol — How This World Is Played

This document is the rulebook for playing the campaign **through Git itself**. It is
written for both the player and the LLM gamemaster. Canonization, lazy loading, and
wiki maintenance remain as defined in `CLAUDE.md` and `meta/conventions.md`; this file
governs **actions, fate, cost, time, and turn order**.

## The five laws

1. **`main` is the canonical timeline.** What is merged is real. History is the
   immutable past of the world.
2. **Every player action is a Pull Request.** Opening a PR declares intent. CI checks
   are the laws of physics. Merging makes the action real.
3. **The GM is a CI job.** After every merged player action, the gamemaster wakes up
   in GitHub Actions, narrates the consequences, canonizes new entities, and opens its
   own world-state PR back at you. Merging the GM's PR is turning the page.
4. **Fate is a hash.** Dice are derived deterministically from the merge commit SHA.
   Nobody — not you, not the GM — can fudge a roll, and anyone can verify one forever.
5. **Changing the world costs Weave.** The bigger the diff against reality, the more
   it costs. Narrating yourself is free; rewriting the laws of the world is not.

## The turn loop

```
player                         github actions                        the world
──────                         ──────────────                        ─────────
branch action/<slug>
edit sessions/ (+ world/, plot/)
open PR (action template)  ──▶ validate.yml:
   with a ```rolls``` block      schema · links · indexes · lint
                                 weave cost comment (fails if too costly)
merge the PR ──────────────▶ gm-turn.yml:
                                 🎲 dice resolved from merge SHA (comment)
                                 GM narrates + canonizes
                                 weave deducted, +2 regen, ledger updated
                            ◀── GM opens PR gm/turn-<N>-pr<num>
read the narration
argue via /gm comments
merge the GM PR ───────────▶ (no-op: the gm-turn label guards the loop)
                                                                  state is canonical
next action…
```

**Table rule: one action in flight at a time.** Don't open a second action PR while a
GM turn PR is still open. The GM enforces this on its side: if a `gm-turn` PR is
already open against the same base, the new turn refuses to run until you merge it.

### Writing an action PR

- Branch from the base you are playing on: `action/<slug>` (e.g. `action/pick-the-lock`).
- Append your action to today's session log `sessions/YYYY-MM-DD-NN.md` — written as
  your character's declared intent, not its outcome. The outcome belongs to fate and
  the GM.
- You *may* edit `world/`, `plot/`, `character/` files directly — that is what Weave
  is for (see the cost table).
- Use the **action** PR template. Declare any rolls in a fenced block in the PR body:

  ````markdown
  ```rolls
  pick-the-lock: 1d20+2   # Dexterity, rusty cellar door
  spot-the-guard: 1d20    # Perception
  ```
  ````

- Merge when you are committed. **The merge is the action.** The roll does not exist
  until you merge — fate is revealed when you commit.

## Dice — provably fair rolls

**Grammar:** `NdS[+M|-M]` with `1 ≤ N ≤ 20`, `S ∈ {2, 4, 6, 8, 10, 12, 20, 100}`,
`0 ≤ M ≤ 99`. Action ids: `[a-z0-9-]{1,40}`, unique within one PR.

**Algorithm.** For die *i* (0-based) of roll `action_id` in PR `pr_number`, with the
merge commit SHA (lowercase hex) as entropy:

```
counter = 0
loop:
  digest = HMAC-SHA256(key = sha_utf8, msg = f"{pr_number}:{action_id}:{i}:{counter}")
  v      = first 8 bytes of digest as big-endian uint64
  if v >= floor(2^64 / S) * S:  counter += 1; continue   # rejection sampling, no modulo bias
  die    = v % S + 1
```

Sum the dice, apply the modifier. Verify any roll ever made:

```
python3 scripts/dice.py --entropy <merge-sha> --pr <number> --id <action-id> --expr 1d20+2
```

Every roll is recorded twice: as a comment on the merged PR, and as a row in the
append-only ledger `meta/rolls.md`.

Why the **merge** SHA and not the head SHA: head SHAs can be ground cheaply
(`--amend`, re-push until you like the roll). The merge commit is created by GitHub at
merge time and cannot be retried without a visible revert in history and in the
ledger. You commit to the action before knowing the outcome.

## Weave — the cost of changing reality

Your character sheet carries two frontmatter fields:

```yaml
weave: 10
weave_max: 10
```

Every action PR's cost is computed from its diff (`added + deleted` lines per file),
summed, with a minimum of 1:

| Paths | Cost | In fiction |
|---|---|---|
| `sessions/`, `character/journal.md` | 0 | narrating yourself is free |
| `plot/`, `character/sheet.md` | ceil(lines / 10) | nudging your own thread |
| `world/**` — editing an existing article | ceil(lines / 5) | reshaping reality |
| `world/**` — creating a new article | ceil(lines / 5) **+ 2** | summoning into existence |
| `meta/canon.md` | ceil(lines / 5) **× 3** | rewriting the laws of the world |
| `meta/seeds.md`, `meta/contradictions.md`, `_index.md` files | 0 | bookkeeping |

CI posts the cost breakdown on every action PR and **fails the check if cost exceeds
your current Weave**. On each GM turn the driver deducts the cost and regenerates
**+2**, clamped to `[0, weave_max]`. If you hit 0, the GM narrates your exhaustion.

Cost is waived for `session-zero` PRs and any time the sheet has no `weave:` field yet
(the game has not started). GM PRs never pay — the GM *is* the world.

## Timelines — branches as alternate realities

Want to explore a what-if without committing reality to it?

- **Fork reality:** `git branch timeline/<slug> main`. Play normally — action PRs
  target `timeline/<slug>` instead of `main`. The GM plays along on that base.
- **Make it real:** open a PR `timeline/<slug> → main` using the **timeline-merge**
  template. If it merges cleanly, that reality wins.
- **Paradoxes:** if the timeline conflicts with what happened on `main` meanwhile, CI
  labels the PR `paradox` and lists the conflicting files as narrative paradoxes.
  Comment `/resolve-paradox` and the GM will resolve each conflict **in fiction**,
  log the paradox in `meta/contradictions.md`, and push the resolution commit. You can
  always resolve conflicts by hand instead — the GM's resolution is an offer, not law.
- **Abandon a timeline:** tag it, then delete the branch:

  ```
  git tag archive/timeline/<slug> timeline/<slug>
  git push origin archive/timeline/<slug> :timeline/<slug>
  ```

- **Salvage from a dead timeline:** `git cherry-pick` a commit from the archive tag
  into a normal action PR. The Weave economy prices it automatically; the GM narrates
  it as a recovered memory or artifact — something that survived a reality that never
  happened.

## Quests, chapters, recaps

- **GitHub Issues are the quest log.** Labels: `quest:active`, `quest:resolved`,
  `quest:failed`, `seed`. The GM opens, comments on, and closes quest issues as part
  of its turns. `plot/active-quests.md` is kept as a one-line mirror (with issue
  links) so the wiki stays self-contained offline.
- **Milestones are chapters.** Assign quest issues to the current chapter milestone.
- **Closing a milestone closes a chapter:** CI asks the GM for a recap, writes
  `sessions/chapter-<N>-recap.md` via a GM PR, tags `chapter-<N>`, and publishes a
  GitHub Release with the recap as notes.

## Comment commands

| Command | Where | Effect |
|---|---|---|
| `/gm <message>` | any PR or issue | Talk to the GM out-of-band: ask questions, argue a ruling, co-author session zero. The GM replies in-thread without changing world state. |
| `/resolve-paradox` | a conflicted `timeline-merge` PR | The GM resolves merge conflicts in fiction and pushes the resolution. |
| `/lint` | any PR or issue | Run the mechanical style checks repo-wide and post the report. |

Note: comment commands run the workflow version on the default branch — changes to
the commands themselves take effect only after they are merged to `main`.

## Session zero — creating the world is the first move

The first act of any campaign is itself a Pull Request:

1. Branch, fill in `meta/canon.md` (genre, tone, hard rules) and `character/sheet.md`
   (who you are; include `weave: 10` / `weave_max: 10`).
2. Open the PR with the **session-zero** template and the `session-zero` label.
3. Co-author with the GM via `/gm` comments until the world feels right.
4. Merge. The GM wakes up and narrates the opening scene as its first PR.

Prefer a ready-made start? Run the **setup** workflow with `seed_demo` enabled and it
materializes the demo campaign as a `demo-campaign` branch plus a starting quest
issue — open the PR `demo-campaign → main`, label it `session-zero`, merge, and play.

## What the GM may and may not touch

The GM's LLM output is applied by a driver script that enforces a path allowlist:

- **May write:** `world/**`, `plot/**`, `sessions/**`, `character/journal.md`,
  `character/sheet.md` (body only — the driver owns the frontmatter math).
- **May never write:** `meta/canon.md` (proposed changes become entries in
  `meta/contradictions.md` for the player to rule on), `meta/rolls.md` (driver-owned
  ledger), the `weave:` fields, `.github/`, `scripts/`.

Dice results, Weave math, turn counters, and ledger rows are computed by
deterministic scripts. The model narrates and canonizes; it does not do arithmetic
and it cannot fudge.

## Setup (one-time)

1. Fork the repo.
2. Create a fine-grained PAT scoped to this repo (Contents RW, Pull requests RW,
   Issues RW) and store it as the secret `GM_GITHUB_TOKEN`. (Without it the GM still
   plays, but its PRs won't get validation checks — GitHub suppresses workflows
   triggered by the default token.)
3. Store the secret `GM_API_KEY` and the repo variables `GM_PROVIDER`
   (`anthropic` or `openai`), `GM_MODEL`, optionally `GM_BASE_URL` (use the `openai`
   provider with a custom base URL for OpenRouter, vLLM, Ollama, llama.cpp, …), and
   optionally `GM_AUTO_MERGE=true` if you want GM PRs to merge themselves.
4. Run the **setup** workflow (Actions → setup → Run workflow). It creates labels and
   the Chapter 1 milestone, sanity-checks your secrets, and can seed the demo.
5. Open your session-zero PR. Welcome to the world.
