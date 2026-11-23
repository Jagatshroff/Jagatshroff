---
name: validate-interview
description: >-
  The Interview Kit. Writes a Mom Test style interview script about the past, not opinions about
  the idea, plus an outreach draft for each prospect built from what that person actually said.
  The user sends them. Use when the user asks for "interview questions", "customer interview
  script", "how do I reach out", "outreach message", or "customer discovery".
argument-hint: "[prospect handle]"
---

# validate-interview

Public complaints tell you what hurts. Interviews tell you what people actually
do about it, what it costs them, and whether they will commit. This skill
writes the script and the first message to each prospect. It never sends
anything. The user does that, by hand, one at a time.

What the user typed after `/validate-interview`: `$ARGUMENTS`

## What it reads

`validator/prospects.md` (who), `validator/pain.md` (the pains to ask about),
`validator/segment.md` (the beachhead), `validator/wtp.md` (what is known about
price) and `validator/idea.json` (the hypothesis and the real-world bar).

Before anything else, rerun `/validate-prospects` so the list is fresh and
honours `validator/do_not_contact.txt`. Never draft for anyone from an old copy
of the list.

If `segment.md` is missing, use the target in `idea.json` and say so. If
`pain.md` shows the evidence bar failed, say that plainly: the interviews are
now the main test of the idea, so treat them that way.

## Step 1: the script, written to validator/interview.md

Follow the Mom Test rules (from Rob Fitzpatrick's book of that name): ask about
their life and their past, never about your idea or their future. People are
polite about ideas and honest about last Tuesday.

Write 8 to 12 questions in this order, worded for this problem and this group:

1. **Context.** "Walk me through how you handle <the area> today."
2. **The last time.** "Tell me about the last time <the top pain> happened."
   Then "what happened next?" and "what did it cost you?" in time, money or a
   lost deal.
3. **What they tried.** "What have you tried to fix it?" "What did you pay for
   that?" "Why did you stop?" Use the tools from `tried` in `themes.json`.
4. **How much it matters.** "Where does this rank among the problems in your
   week?" "Who else is affected?"
5. **The money, last.** "What do you spend on <the area> today, in tools and
   in time?" Never "would you pay for X".
6. **The commitment ask, at the very end.** Something that costs them a little:
   joining a waitlist, a second call to try an early version, an introduction
   to a colleague, or a refundable preorder if `/validate-smoke` set one up.

Then list the questions to avoid, so the user catches themselves: "would you
use...", "do you like the idea...", "how much would you pay for...", and any
question that describes the product.

End `interview.md` with a notes template for each call: date, person (their
handle, not a real name, unless they offer it), their exact words on the pain,
how they handle it today, what it costs, what they already pay, and the
commitment they gave (none, time, an intro, money).

Add the privacy rules to the top of the template: ask before recording a call,
keep notes in `validator/interviews/`, keep `validator/` out of any public git
repository, and delete the notes when the validation is over or within 90 days.

## Step 2: one draft per prospect, written to validator/outreach.md

For each person the user picks from `prospects.md` (suggest 5 to 10 who fit
the target, and say so if none do):

- Open with **their own post**: link it and name the specific thing they said.
  Use their quote only as it appears in `prospects.md`.
- Say who the user is in one honest line: their real name, that they are
  researching this problem, and that they may build something for it ("I'm
  exploring whether to build something for this"). People deserve to know why
  they are being asked.
- Ask for one thing: 15 minutes to hear how they handle it today.
- **No pitch, no product name, no link to a product**, and no claim that
  anything exists yet.
- Give an easy way out: "no worries at all if not".
- Keep it under 80 words. Write each one for that person, about what they
  actually said. It is a message to a human, not a campaign.

Add a line per draft on how to reach the person on their platform:

- **Reddit**: a chat or private message to the handle, or a public reply in the
  thread if the post is under 30 days old and the subreddit allows it. Read the
  subreddit's rules first (with web tools if you have them, otherwise list it as
  a step for the user). Many ban research requests in comments.
- **Hacker News**: there are no private messages. Use contact details only if
  the person put them in their own HN profile. Never go looking elsewhere for an
  email address.
- **X and other imports**: a reply, or a DM if their DMs are open.

Tell the user the sending rules:

- By hand, at most 5 a day.
- One message per person. No follow-up if they do not answer: silence is an
  answer.
- Stop the moment anyone asks not to be contacted, add them to
  `validator/do_not_contact.txt`, and delete their draft.

## Step 3: after the interviews

When the user brings back notes (pasted, or files in `validator/interviews/`):

1. Count the commitments by type, and compare them with the interview part of
   `bar.real_world` in `idea.json` (for example "30% say they would pay").
2. Pull out what surprised: pains the mined data missed, prices people named,
   tools they use.
3. Quote people only with their permission, and only as the user's notes have
   it, marked as interview notes, not as verified posts.

## Never

- Send, post, like, follow or DM anything yourself.
- Write a message that pretends to be from someone else, or hides that the
  user is researching a product.
- Use a prospect's words as a testimonial.

## Output

`validator/interview.md`, `validator/outreach.md`.

Next: `/validate-smoke` puts a page and a price in front of real people.
