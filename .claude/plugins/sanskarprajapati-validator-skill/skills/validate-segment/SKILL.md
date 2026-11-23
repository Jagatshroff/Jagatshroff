---
name: validate-segment
description: >-
  The Beachhead picker. Reads who is behind the top pains: their role, their context, the tools
  they already pay for and how often they complain. Picks the one group to build for first, with
  the evidence for and against. Use when the user asks "who is my customer", "who should I
  target", "which niche first", "pick a beachhead", or "who feels this most".
argument-hint: "[theme]"
---

# validate-segment

A startup that sells to everyone sells to no one. This skill picks the one
group to build for first: the people who feel the top pain hardest, already
spend money on it, and can be found. The table comes from a script. The
choice is yours to argue, but only from that table and from real quotes.

What the user typed after `/validate-segment`: `$ARGUMENTS`

## The tool

```bash
python3 "${CLAUDE_SKILL_DIR}/segments.py" [--dir validator] [--min 3]
```

If the path is not expanded, use the base directory Claude Code printed for
this skill. It needs `validator/labels.jsonl`, so run `/validate-cluster` first.
`/validate-pain` should have run too, because you will need `pain.md`.

## Step 1: run the table

Run `segments.py`. It writes `validator/segments.md` and `segments.json` with two
cuts of the same complaints:

- **By stated role**: what the post says the writer does (recruiter, founder).
  Plurals and articles are merged ("Recruiters", "a recruiter").
- **By community**: where it was said (a subreddit, Hacker News, an app's
  reviews). Most posts never state a role, so the place is often the better
  clue to who someone is.

Each group shows its size, how many different people, money and workaround
signals (the same rules as the Pain Index), intensity and its top themes.
Lower `--min` to 2 if the data is small, and say that you did.

## Step 2: pick one beachhead

Read `segments.md` and `pain.md`. Pick ONE group by these four tests, in order:

1. **Feels a pain worth money.** Their top themes are the ones `pain.md` rated
   worth money or real.
2. **Already spends.** Money signals, and tools they named in `tried`
   (`themes.json`). A group with workarounds and no money talk is a maybe.
3. **Can be reached.** A community you can post in, or a role you can search
   for on LinkedIn. A group you cannot find is not a beachhead.
4. **Is big enough to matter**, now or as a first step to a bigger group.

If `idea.json` names a target and the data points elsewhere, say so plainly,
with the numbers. Do not edit `idea.json` yourself. The user decides whether to
change the target.

## Step 3: write validator/segment.md

```
# Beachhead: <group>

Why them: <the numbers from segments.md: complaints, people, money, workaround, top theme>
Against: <what is weak: small, few money signals, hard to reach, mostly one community>
In their words: <two or three quotes, each with its ID and link>
Runner-up: <the next group and why it lost>
Where to find them: <communities, job titles, events, newsletters, with links where known>
```

Quotes come only from the `quote` field in `labels.jsonl` (look them up with
`python3 "${CLAUDE_SKILL_DIR}/../validate-mine/store.py" show <id>` for the link),
or from `pain.md`. Those passed a word-for-word check. Anything you put in your
own words goes without quotation marks.

Mark every "where to find them" item you did not see in the data as a
suggestion, not a finding.

## Step 4: tell the user

Give them the beachhead in one line, the strongest number for it, the strongest
number against it, and the runner-up. Ask whether they agree before
`/validate-wtp` prices for that group.

## Honest limits, say them once

Roles come only from what people chose to say about themselves, so the role
cut is small and skews towards people who introduce themselves. Communities
are a proxy: not everyone in r/recruiting is a recruiter. Treat the beachhead
as the best bet from public talk, to be confirmed in interviews
(`/validate-interview`).

## Output

`validator/segments.md`, `validator/segments.json`, `validator/segment.md`.

Next: `/validate-wtp` reads what this group says about money.
