---
name: validate-cluster
description: >-
  The Pain Mapper. Sends the mined complaints to sub-agents in batches of 50, each one labelling
  every complaint with a pain theme, who is speaking and what they tried, then merges the labels
  into a short list of themes with counts. Use when the user says "group the complaints",
  "what are the themes", "cluster this", "map the pain", or after /validate-mine finishes.
argument-hint: "[--batch 50]"
---

# validate-cluster

The miner keeps everything that matches the search. This skill sorts it: which
posts are real complaints about the problem, which pain each one describes, who
is speaking and what they already tried. Sub-agents do the reading. One shared
codebook keeps their themes consistent, and a tool checks every label, so
nothing gets in on trust.

What the user typed after `/validate-cluster`: `$ARGUMENTS`

## The tools

```bash
python3 "${CLAUDE_SKILL_DIR}/batches.py" <command>               # plan, check, save, tally
python3 "${CLAUDE_SKILL_DIR}/../validate-mine/store.py" sample   # read complaints
```

Below, `BATCHES` and `STORE` mean exactly those. If the path is not expanded,
use the base directory Claude Code printed for this skill. State lives in
`validator/cluster/`. The codebook shape is in
`${CLAUDE_SKILL_DIR}/codebook.example.json`.

## Step 1: the codebook

Needs `validator/complaints.jsonl`. If it is missing, run `/validate-mine` first.

Read a sample yourself:

```bash
STORE sample --n 80 --seed 1
```

Write `validator/cluster_codebook.json` with 5 to 10 themes. Each theme is a
pain, a thing that goes wrong for the person, not a feature they want and not
a product category:

- `key`: lowercase with dashes (`missed-replies`). Never `other`.
- `name`: a few plain words.
- `definition`: one line saying what belongs in it, sharp enough that two
  people would put the same post in the same theme.

Use the sample's own words. Merge themes that differ only in wording. Show the
user the list and let them correct it before you spend anything on labelling.

## Step 2: plan the batches and say what it costs

```bash
BATCHES plan --batch 50
```

It writes one brief per batch and lists them in waves of 10. Tell the user how
many sub-agent calls this is (one per batch: 1,000 complaints is 20 calls) and
that each sub-agent writes one file, so accept-edits mode (Shift+Tab) saves an
approval per batch. If batches already exist, `plan` refuses. `--fresh` starts
over and throws the old labels away, so ask first.

## Step 3: run the waves

For each wave, send ONE message with one Agent tool call per batch in it (the
tool is called Task in older Claude Code versions):

- `subagent_type`: `general-purpose`
- `description`: `label <batch>`
- `prompt`: `Read <brief path> and follow it exactly. It is your whole brief.`

Wait for the whole wave before starting the next. Then:

```bash
BATCHES check
```

It lists every batch that is missing or broken, and why: an unknown theme, a
missing post, or a quote that is not word for word from the post. Run the
broken batches once more. If a sub-agent printed its JSON instead of writing
the file, save its reply with `BATCHES save <batch>` and the reply on stdin.
`save` refuses anything that fails the checks. A batch that fails twice is left
out. Never write or fix a label yourself, not even one.

## Step 4: tally

```bash
BATCHES tally                    # every batch must pass check
BATCHES tally --allow-missing    # leave failed batches out, and say so
```

This writes `validator/themes.json` and `validator/labels.jsonl`.

If more than one complaint in ten landed in `other`, the codebook is missing
something. Read the `new_theme` names in `themes.json`, add 1 to 3 themes to the
codebook (add only; never rename or remove a key that labels already use),
then label just those complaints again and tally:

```bash
BATCHES plan --only-other
BATCHES tally
```

## Step 5: tell the user

1. How much of the haul was signal: complaints out of everything mined, and
   the main kinds of noise (launches, ads, other meanings of the words).
2. The themes with counts, biggest first, and the roles that show up most.
3. What people already tried (`tried` in `themes.json`). Workarounds are the
   strongest clue that a pain is worth money.
4. Anything left out: failed batches, complaints still in `other`.

Spot-check five labels yourself against `STORE show <id>` before you report.
If they look wrong, the codebook definitions are too loose. Sharpen them and
label again with `--fresh`, after asking.

## Honest limits, say them once

Language models label well but not perfectly. Some borderline posts will land
in the wrong theme, and relevance calls vary at the edges. The quotes are
checked word for word, so whatever a later report quotes was really said. The
counts are close, not exact.

## Output

`validator/cluster_codebook.json`, `validator/cluster/` (batches, briefs,
labels), `validator/themes.json`, `validator/labels.jsonl`.

Next: `/validate-pain` scores each theme.
