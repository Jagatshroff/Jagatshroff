---
name: validate-pain
description: >-
  The Pain Index. Scores every pain theme on frequency, intensity, recency, money signals ("I'd
  pay", a price, "switched from") and workaround signals (a script, a spreadsheet, an assistant
  hired for it), with fixed published rules so the same data always gets the same score. Ends
  with the pains worth money and the ones that are only noise. Use when the user asks "which
  problem is worth solving", "how bad is the pain", "score the pain", or "is this a real
  problem".
argument-hint: "[--top 3]"
---

# validate-pain

The Pain Index turns labelled complaints into a ranking you can defend. Every
number comes from fixed rules in a script, so nobody can talk a pet theme up
the list, you included.

What the user typed after `/validate-pain`: `$ARGUMENTS`

## The tool

```bash
python3 "${CLAUDE_SKILL_DIR}/painindex.py" [--dir validator] [--today YYYY-MM-DD]
```

The signal rules (the exact words that count as money, workaround or intensity)
are in `${CLAUDE_SKILL_DIR}/signals.py`. If the path is not expanded, use the
base directory Claude Code printed for this skill.

## Step 1: run it

Needs `validator/labels.jsonl` and `validator/themes.json`. If either is missing,
run `/validate-cluster` first. If `validator/idea.lock` exists, run
`python3 "${CLAUDE_SKILL_DIR}/../validate-idea/idea.py" check validator/idea.json`
first. If the bar moved without a recorded reason, stop and tell the user.

The index only counts complaints inside the bar's `max_age_months` window. It
writes `validator/pain.md` (the report), `validator/pain.json` (every number)
and `validator/signals.jsonl` (which signal fired on which complaint, and the
words that fired it).

## How the score works, say it once

Six parts, each from 0 to 1, weighted to a score out of 100:

| part | weight | what it measures |
| --- | --- | --- |
| money | 30 | share of complaints that mention paying, a price, a refund or switching tools |
| frequency | 20 | how many complaints, against the biggest theme |
| intensity | 15 | the labellers' 1-3 rating, plus strong words and shouting |
| workaround | 15 | share that describe a spreadsheet, a script, a hire, manual copying |
| breadth | 10 | how many different people and communities say it |
| recency | 10 | share from the last six months |

Money weighs most, because complaining is free and paying is not. A theme needs
at least 10 complaints to be called, and at least 60 points with 3 money signals
to be called **worth money**. Below 40 is **noise**. In between is **real,
unproven**.

## Step 2: tell the user

Read `validator/pain.md`, then give:

1. The bar: complaints and money signals, need against have, pass or fail.
2. The ranking: each theme's score and tier in one line.
3. For each theme worth money (up to three): what the pain is, who has it, and
   one quote exactly as `pain.md` gives it, with its ID and link.
4. The noise: which themes scored low and why (one loud person, no money talk,
   all old).
5. What is thin: themes marked too few to call, and complaints still in `other`.

Quote only from `pain.md` or `labels.jsonl`. Those quotes passed a word-for-word
check against the original posts. Never paraphrase a quote inside quotation
marks.

## Step 3: if you disagree

You may think a score is off, for example a theme full of sarcasm the word rules
read as money talk. Say so in words, with the complaint IDs that show it. Never
change a score, a tier, a weight or a rule to make a theme rank differently. A
rule change is a change to the pack, made in `signals.py` with tests, never in
the middle of a run.

## When the bar fails

Say it plainly: the evidence does not clear the bar the user set before seeing
any data. Then offer the two honest ways forward. One is to mine more: different
pain phrases, more communities, the competitors' reviews. The other is to narrow
the idea to the theme or group that scored best, and test that. Do not move the
bar to make it pass. If the user decides to move it, that is their call, and
`idea.py lock --reason` records it.

## Output

`validator/pain.md`, `validator/pain.json`, `validator/signals.jsonl`.

Next: `/validate-segment` picks who to build for first.
