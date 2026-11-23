---
name: validate-idea
description: >-
  Intake for the Validator pack. Turns a startup idea into validator/idea.json: the target user,
  the problem hypothesis, the search terms and competitor apps to mine, and the pass/fail bar,
  which is set before any data comes in and never moved after. Use when the user says "validate
  my idea", "is this idea any good", "test this startup idea", "should I build this", or
  starts the Validator pack.
argument-hint: "[the idea in one line]"
---

# validate-idea

The first skill in the pack. It does one job: pin the idea down tightly enough
that the rest of the pack can test it, and set the pass/fail bar before anyone
has seen a single complaint. People who set the bar after seeing the data always
find a reason to pass.

What the user typed after `/validate-idea`: `$ARGUMENTS`

## The tool

```bash
python3 "${CLAUDE_SKILL_DIR}/idea.py" check validator/idea.json
python3 "${CLAUDE_SKILL_DIR}/idea.py" lock  validator/idea.json
```

Below, `IDEA` means `python3 "${CLAUDE_SKILL_DIR}/idea.py"`. If the path is not
expanded, use the base directory Claude Code printed for this skill. The shape
of the file is in `${CLAUDE_SKILL_DIR}/idea.example.json`.

## Step 1: the idea, the person, the problem

If `$ARGUMENTS` is empty, ask for the idea in one line. Then ask, one question at
a time, only for what is still missing:

- **Who** has the problem. Push for a role and a context, not a demographic.
  "Small businesses" is too wide. "Solo recruiters who work leads over email,
  LinkedIn and WhatsApp" is something you can search for.
- **What goes wrong** for them today, in their words. A missed reply, a lost
  hour, a bill they hate. Not the absence of your product.
- **What they do about it now.** The workaround is the best clue there is.

If the user already knows this from their own customers, use it and say which
parts came from them and which are your guesses.

## Step 2: the hypothesis

One sentence the data can prove wrong:

> [who] struggle with [problem] and would pay [rough price] for [outcome].

If the user has no price in mind, leave a range and say `/validate-wtp` will
test it.

## Step 3: what to search for

Write `search.terms` the way a frustrated person would type a post, not the way
a landing page talks. Three to eight terms. Quote exact phrases:
`"unified inbox"`, `"too many messaging apps"`. A term without quotes matches
posts that contain every word, in any order.

Good terms name the pain or the workaround: `"missed a message"`, `"spreadsheet
to track"`, `"switched from <competitor>"`. Bad terms are your product category
in marketing language, because nobody complains in that voice.

`search.subreddits` (optional): communities where this person hangs out.
`search.competitor_apps` (optional): apps people already use for this. Look up
each App Store id with the miner's search:

```bash
python3 "${CLAUDE_SKILL_DIR}/../validate-mine/sources.py" find-app "<app name>"
```

Pick the right one from the list with the user. A wrong id mines the wrong app.

## Step 4: the bar

Explain this once: the bar is what the evidence must show for the idea to
pass, and it is set now because nobody judges fairly after seeing the data.

`bar.evidence` is what the mined data has to show:

- `min_complaints`: distinct complaints about this problem. Default 100.
- `min_money_signals`: complaints that mention paying, a price, or switching
  tools. Default 10. This is the number that matters most.
- `max_age_months`: only count complaints this recent. Default 24.

`bar.real_world` is what a real test has to show later (`/validate-smoke`
plans it). Ask the user, and suggest numbers if they have none, for example
"200 waitlist signups from strangers" and "10 paid, refundable preorders".

## Step 5: write, check, lock

1. Write `validator/idea.json` in the shape of the example.
2. Run `IDEA check validator/idea.json` and fix everything it lists.
3. Show the user the idea, the hypothesis, the terms and the bar in a few
   lines. Let them correct it.
4. Once they agree, run `IDEA lock validator/idea.json`.

After the lock, terms, subreddits and apps can still change freely. The bar
cannot. If the user later wants to move it, run `IDEA lock ... --reason "<why>"`.
The move is kept in `validator/idea.lock`, and `/validate-verdict` reports it.
Never edit `idea.lock` by hand, and never move the bar without the user asking.

## Output

`validator/idea.json`, `validator/idea.lock`.

Next: `/validate-mine` reads the search terms and competitor apps.
