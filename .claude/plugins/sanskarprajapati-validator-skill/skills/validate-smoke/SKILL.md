---
name: validate-smoke
description: >-
  The Smoke Test. Writes landing page copy in the complainers' own words, a waitlist or preorder
  plan, where to share it, and the numbers to watch against the bar in validator/idea.json. Use
  when the user asks for "a landing page", "a waitlist", "a smoke test", "a demand test",
  "preorders", or "how do I test demand for real".
argument-hint: "[--channel waitlist|preorder]"
---

# validate-smoke

Everything so far is talk. A smoke test asks strangers to do something that
costs them a little: leave an email, or put down a refundable deposit. This
skill writes the page copy from the words people already used, plans where
to show it, and fixes the numbers that count as a pass before the page goes up.

What the user typed after `/validate-smoke`: `$ARGUMENTS`

## What it reads

`pain.md` (the pain), `segment.md` (who), `wtp.md` (price), `competitors.md` and
`gaps.md` (what to be different on), and `idea.json` (`bar.real_world`, the
real-world part of the bar, set on day one).

When something is missing, say so and carry on with what is there:

- No `segment.md`: write for the target in `idea.json`.
- No `competitors.md`: use `gaps.md`. If neither has an open gap, leave out the
  "different from" line rather than inventing one.
- The evidence bar failed in `pain.md`: say it plainly. The smoke test can still
  run, as the real-world half of the bar, but suggest narrowing the idea to the
  best-scoring theme or group first.

## Step 1: pick the test

- **Waitlist**: an email signup. Cheap and fast, but a weak signal.
- **Preorder**: a refundable deposit or a discounted first year. A strong signal.
  It needs a payment link the user sets up themselves.

Use what `bar.real_world` asks for. If it names both (say 200 signups and 10
preorders), the page offers the waitlist with a preorder option. If the user
asked for a waitlist only but the bar needs preorders, point out that a
waitlist alone cannot pass that bar, and let them choose.

## Step 2: the page copy, in validator/smoke.md

Write it in the beachhead's words, not in startup language:

- **Headline**: the top pain in plain, everyday words, the kind that repeat
  across the quotes in `pain.md` ("too many apps", "missed messages"). Never lift
  a distinctive phrase from one stranger's post: that is their voice, not yours.
- **Subhead**: the outcome they want, in one line.
- **Three pains** they will recognise. List the complaint IDs each one rests on
  in a separate "Evidence" section of `smoke.md`, never in the page copy or its
  HTML. Those IDs lead back to strangers' posts, and a live page is public.
- **How it will work**: three steps, clearly labelled as what is being built,
  not what exists.
- **Price**: from the range in `wtp.md`. If there is no range, test the two ends
  of the price in the hypothesis in `idea.json` on two versions of the page, and
  label them as the user's guesses, not findings.
- **The ask**: the waitlist field and/or the preorder button, with the refund
  terms in plain words next to it, and one line on what the email is used for
  ("we will only email you about this"). Refund terms are the user's to set:
  mark any you draft as a suggestion.
- **Questions people will have**: answer the top objections from `pain.md` and
  `wtp.md` (privacy, price, "does it work with X").
- **Different from**: one line on the open gap from `gaps.md`, without naming or
  running down competitors in ways the user could not back up.

Rules for the copy:

- No testimonials, no "trusted by", no user counts, no logos. Nothing exists yet.
- No fake scarcity ("only 20 spots"), no countdowns, no invented team, and no
  delivery date the user has not committed to.
- Never use a complaint from the mined data as a quote on the page. Those
  people did not agree to be on it.
- Say plainly that it is early ("we are building this; join to get it first").
- A preorder must say it is refundable, and how.

## Step 3: where to share it, in smoke.md

List each place with how to post there within its rules:

- The beachhead's communities. Read each one's self-promotion rules and link
  them. Many allow a link only in a weekly thread, or not at all.
- The interviewees who asked to see it.
- The user's own accounts.

Write each post as an honest note from the person building it: what they
learned about the pain, that they are building something, and the link, in
places whose rules allow that. Never write a post that hides that the writer
is the builder. The user posts them. You never post anything.

Do not add interviewees to the waitlist. Send them the link only if they asked
to see it.

## Step 4: the numbers, fixed now

Before the page goes live, write into `smoke.md`:

- The pass line, copied from `bar.real_world`, unchanged.
- The test window: 14 days, or until a set number of visitors.
- What to measure: unique visitors, signups, signup rate, preorders, and where
  each came from.
- The decision, written now: pass, narrow (one group or theme did well), or
  kill.

If the user wants a typical signup rate to compare with, label it as outside
knowledge, not data from this run.

## Step 5: building the page

Building and hosting the page is a separate job. Offer to write a simple page
in the user's own project, or point them to a no-code page builder and a form
tool. The user creates any accounts, domains and payment links themselves. Never
create accounts, deploy, or set up payments for them.

## Afterwards

When the user brings back the numbers, compare them with the pass line exactly
as written in Step 4, and record the result in `smoke.md`. `/validate-verdict`
reads it.

## Output

`validator/smoke.md`.

Next: `/validate-verdict` puts the idea on trial.
