---
name: validate-competitors
description: >-
  Competitor Gaps. Maps who already solves the top pain, their prices and positioning, then mines
  what their own users complain about in public reviews and threads. The complaints competitors
  leave unsolved are the gap. Use when the user asks "who else does this", "competitors",
  "is this already solved", "what's the gap", or "how do I beat X".
argument-hint: "[competitor names]"
---

# validate-competitors

"Is this already solved?" is the wrong question. Something always exists. The
right question is what the people who use it still complain about. This skill
mines each competitor's own users with the same tools and the same codebook as
your main run, so the two line up theme by theme.

What the user typed after `/validate-competitors`: `$ARGUMENTS`

## The tools

```bash
python3 "${CLAUDE_SKILL_DIR}/gapmap.py" [--dir validator]
python3 "${CLAUDE_SKILL_DIR}/../validate-mine/sources.py" --dir <folder> <command>
python3 "${CLAUDE_SKILL_DIR}/../validate-cluster/batches.py" --dir <folder> <command>
```

If the path is not expanded, use the base directory Claude Code printed for
this skill. Below, `MINE`, `BATCHES` and `GAPMAP` mean these three.

## Step 1: pick 2 to 4 competitors

Start from what the data names: `search.competitor_apps` in `idea.json`, the
`tried` lists in `themes.json`, and tools named in `wtp.md`. Add any the user
names. Ask the user to confirm the list. Each one costs a mining run and one
labelling sub-agent per 50 complaints.

## Step 2: the facts, each with a source

For each competitor, find what it does, who it is for, its price and its
platforms. Use web search and the competitor's own pages. Every fact gets the
link it came from and today's date. If you cannot find a fact, write
"unknown". Never fill it in from memory: prices change, and a wrong price in a
report is worse than a blank.

## Step 3: mine each one

Use a short lowercase slug (`beeper`). For each competitor:

```bash
mkdir -p validator/competitors/<slug>
cp validator/idea.json validator/cluster_codebook.json validator/competitors/<slug>/
MINE --dir validator/competitors/<slug> appstore --app <id> --name '<Name>'
MINE --dir validator/competitors/<slug> reddit --query '"<Name>"' --since <SINCE> --max 300
MINE --dir validator/competitors/<slug> hn --query '"<Name>"' --since <SINCE> --max 200
```

Use `find-app` to get the App Store id. Skip sources that do not apply. The same
rules as `/validate-mine` hold: run the calls one at a time, keep partial runs,
and never type posts in by hand.

## Step 4: label each one with the same codebook

```bash
BATCHES --dir validator/competitors/<slug> plan --batch 50
```

Run the waves exactly as in `/validate-cluster`, then `check` and `tally` with
the same `--dir`. Never edit the codebook copy in a competitor folder. The gap
map refuses a competitor labelled with a different one, because the themes
would not line up. If the main codebook changes, copy it again and relabel with
`--fresh`.

## Step 5: the gap map

```bash
GAPMAP
```

It writes `validator/gaps.md` and `gaps.json`. For each of your themes it shows
your pain score and the share of each competitor's complaints about it, then a
status:

- **open gap**: you scored it as real, and at least a tenth of a competitor's
  complaints are about it. Their users still hurt here. This is where to win.
- **they struggle too**: their users complain, but your data did not score it
  as real.
- **maybe solved**: under 3% of every competitor's complaints, with enough data.
- **unclear**: anything else, including a competitor with fewer than 20
  complaints.

It also lists what their users complain about that your codebook does not
cover. Read that list. A new theme there can be a gap you have not seen yet.

## Step 6: write validator/competitors.md

1. A facts table: name, what it does, who for, price, link, date checked.
2. The gap map summary: open gaps first, each with one quote from `gaps.md`.
3. What their users raise outside your codebook.
4. A one-line position: "For <beachhead> who <top pain>, unlike <competitor>,
   whose users say <quoted complaint>."

Quote only from `gaps.md`. Those quotes passed a word-for-word check.

## Honest limits, say them once

Shares are of complaints, not of users: a happy majority writes nothing.
App Store reviews come from one country and default to 3 stars and below. A
competitor with few complaints may be small rather than good. "Maybe solved"
means quiet, not proven.

## Output

`validator/competitors/<slug>/` for each competitor, `validator/gaps.md`,
`validator/gaps.json`, `validator/competitors.md`.

Next: `/validate-prospects` finds the people to interview.
