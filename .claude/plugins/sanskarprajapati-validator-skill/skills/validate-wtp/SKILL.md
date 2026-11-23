---
name: validate-wtp
description: >-
  The Price Reader. Pulls every price, current spend, "too expensive" and "I'd pay" line out of
  the mined complaints, normalises them to monthly USD, and turns them into a price range built
  from real words rather than guesses. Use when the user asks "what should I charge", "would
  people pay", "willing to pay", "how much is this worth", or "price this".
argument-hint: "[--theme KEY] [--community NAME]"
---

# validate-wtp

Most founders guess their price. This skill reads it. Every price anyone
mentioned in the relevant posts is pulled out by a script, sorted into would
pay, already pay and too expensive, converted to a monthly figure, and turned
into a range. Where there are too few prices, it says so instead of guessing.

What the user typed after `/validate-wtp`: `$ARGUMENTS`

## The tool

```bash
python3 "${CLAUDE_SKILL_DIR}/wtp.py" [--dir validator] [--theme KEY] [--community NAME] [--all-posts]
```

If the path is not expanded, use the base directory Claude Code printed for
this skill. It needs `validator/labels.jsonl` (`/validate-cluster`). It reads
posts labelled relevant, not only complaints, because "I pay $99 a year for X
and it's fine" is a price signal too.

## Step 1: run it three ways

1. All relevant posts: `wtp.py`
2. The top theme from `pain.md`: `wtp.py --theme <key>`
3. The beachhead, if `segment.md` picked a community: `wtp.py --community <name>`

Each run overwrites `validator/wtp.md` and `wtp.json`, so run the one you will
report on last, or copy the numbers you need as you go.

## How it reads a price, say it once

- It finds an amount with a currency ($, €, £, ₹, "dollars", "bucks", USD...)
  and a period ("/mo", "a year", "per seat per month", "weekly").
- It converts to USD a month with the fixed rates printed in `wtp.md`. A yearly
  price is divided by 12. A lifetime price, or one with no period, is listed but
  kept out of the range.
- It sorts each price by the words around it: **would pay** ("I'd pay"),
  **pays** ("I'm paying", "costs me"), **too expensive** ("overpriced",
  "nobody would pay"), or a plain **mention**. Mentions of company funding
  ("raised $5 million") are never prices.
- **The range** is the middle half of what buyers pay or would pay. If three or
  more people object to a price, the top is capped where the objections start.
  It needs at least 5 buyer prices, or it gives no range at all.

## Step 2: tell the user

1. The counts: would pay, pays, too expensive.
2. The range and its confidence, or that there are too few prices to call one.
3. What people pay today: the named tools and amounts, from the table.
4. Where the objections start.
5. How this compares with the price in the hypothesis in `idea.json`.

Quote only from the "In their words" section of `wtp.md`. Those snippets passed
a word-for-word check. Every amount you name must be in the table.

## When there are too few prices

That is a finding, not a failure: people complain about this problem without
talking about money. Two ways to get more:

- Mine money talk directly with `/validate-mine`, for example
  `'"would pay" <problem words>'`, `'"<competitor>" pricing'` and
  `'"<competitor>" "too expensive"'`. Then label the new posts
  (`batches.py plan --add-new`, run the waves, `tally`) and run `wtp.py` again.
- Ask in interviews (`/validate-interview`), where price questions belong anyway.

Never fill the gap with industry benchmarks or your own sense of what similar
tools cost, unless you label it clearly as outside knowledge, not data.

## Honest limits, say them once

What people say they would pay is not what they pay: treat "would pay" as an
upper bound. Prices in complaints skew towards people who already find a tool
expensive. A range from fewer than 15 prices is a sketch. The real test is a
price on a landing page or a preorder (`/validate-smoke`).

## Output

`validator/wtp.md`, `validator/wtp.json`.

Next: `/validate-competitors` shows what they pay for today and what is missing.
