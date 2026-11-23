---
name: validate-prospects
description: >-
  The Prospect List. Lists the people who described the pain in public: handle, platform, a short
  quote and the link, filtered to the beachhead and ranked by money talk, intensity and how often
  they posted. It is for interviews, and it never sends, follows or messages anyone. Use when the
  user asks "who should I talk to", "find people to interview", "find early users", or "build a
  prospect list".
argument-hint: "[--max 50]"
---

# validate-prospects

The best first interviewees already told the internet about the pain. This
skill lists them, one row per person, each with their own words and the link
to where they said it. A script builds the list from the mined data only, so
nobody on it is invented and no quote is put in their mouth.

**It never sends, follows, likes or messages anyone.** It writes a list.

What the user typed after `/validate-prospects`: `$ARGUMENTS`

## The tool

```bash
python3 "${CLAUDE_SKILL_DIR}/prospects.py" [--dir validator] [--theme KEY] [--community NAME] [--role ROLE]
                                           [--sources reddit,hn,import] [--max 50]
```

If the path is not expanded, use the base directory Claude Code printed for
this skill. It needs `validator/labels.jsonl` (`/validate-cluster`).

## Step 1: run it for the beachhead

Read `validator/segment.md`. If it does not exist, use the target in
`idea.json` and say that no beachhead has been picked yet (`/validate-segment`).
Run the tool filtered to the beachhead: `--community` if the beachhead is a
community, `--role` if it is a role, and `--theme` for the top pain if the list
is long. Then run it once without filters to see how big the wider pool is.

If nobody on the list fits the target, say so plainly. A list of people from
unrelated communities is a finding about the data, not a list to work through.

What it does, say it once:

- **One row per person.** `@Foo`, `u/foo` and `foo` are the same person. It
  keeps their best quote: money talk first, then the most intense, then the
  newest. Every quote is checked word for word against their post. A person
  with no checkable quote is left out. Emails and phone numbers inside quotes
  are hidden in the report.
- **Bots never appear.** AutoModerator and other bots are dropped, at mining
  and again here.
- **The money column shows its evidence**: the exact words that counted as
  money talk, so the user can judge them.
- **Only people you can reach.** Deleted and anonymous authors are left out.
  App Store reviewers are left out by default (`--sources` can add `appstore`),
  because there is no way to contact them.
- **Profile links** only for Reddit and Hacker News handles that look like real
  handles.
- **Old posts** (over 18 months) are marked, because people rarely answer about
  something they wrote that long ago.
- **`validator/do_not_contact.txt`**: one person per line, written any common
  way (`jane`, `@jane`, `u/jane`, or a profile link), with optional `# notes`.
  Anyone on it is left out of every list, for good.

## Step 2: tell the user

1. How many people are on the list, and how many were left out and why.
2. The top ten: handle, where, role if stated, whether they talked about money,
   and their words with the link.
3. How many are recent (not marked old).
4. Which platforms they are on, and what that means for reaching them
   (`/validate-interview` covers how).

Do not look anyone up beyond the post and the public profile the list links
to. Do not search for their email, their employer, their real name or their
other accounts, and do not search for the same handle on other sites. Never
use contact-finding or enrichment tools on anyone from this list (Apollo,
Lusha, people-search sites, or any similar tool installed in this session),
even if the user asks. People told a forum about a problem, not the whole
internet about themselves.

## When someone asks not to be contacted

If the user reports that someone declined or asked to be left alone, add their
handle to `validator/do_not_contact.txt` right away, rerun the list, and delete
that person's draft from `validator/outreach.md` and any notes about them.

## Honest limits, say them once

The list is only as broad as the mined data: people who post about problems,
on the sites that were mined, who did not delete their account. Many of them
will not answer. That is normal. Plan for one reply in five or ten.

## Output

`validator/prospects.md`, `validator/prospects.json`.

Next: `/validate-interview` writes the script and the first messages.
