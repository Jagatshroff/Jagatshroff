# The Validator skill

Eleven Claude skills that test a startup idea against real complaints before you
build it. Free, MIT, no signup, no API key, nothing to connect.

One of them mines up to 1,000 posts where people complain about your problem, from
Reddit, Hacker News and app reviews. One scores how much that pain is worth, with
fixed rules, so nobody can talk a pet theme up the list. One reads every price
people mention and turns it into a range. And the last one puts your idea on
trial: a prosecutor argues it is dead, a defense argues it lives, and a judge
rules go, test, narrow or kill. Any argument that does not cite a real post is
struck out before the judge sees it.

Instead of asking simulated buyers, it reads up to a thousand real ones.

**Every quote is checked to be real text from the post it cites, and it never
posts, DMs or emails anyone.** It reads public posts and writes files. Contacting
people is your call.

## Install

Paste this into Claude:

```
https://github.com/sanskarprajapati/validator-skill

install skill
```

Or as a plugin, in Claude Code:

```
/plugin marketplace add sanskarprajapati/validator-skill
/plugin install validator-skill@validator-skill
```

Claude Code namespaces plugin skills, so installed as a plugin they show up as
`/validator-skill:validate-idea` and so on. Copy the folders instead if you want
plain `/validate-idea`:

```bash
git clone https://github.com/sanskarprajapati/validator-skill.git
cp -r validator-skill/skills/validate-* ~/.claude/skills/
```

Install all eleven together: the later skills use the tools in the earlier ones.
Project-local instead of global: copy the same folders into your repo's
`.claude/skills/`.

It needs Claude Code, because the labelling and the trial run sub-agents, and
Python 3.8 or newer (tested on 3.14). Nothing to pip install.

## First run

1. Open Claude Code in any project folder and type `/validate-idea`. Describe the
   idea in a line. It asks who has the problem, helps you pick search terms, and
   locks your pass/fail bar in `validator/idea.json`.
2. `/validate-mine` collects the posts (5 to 10 minutes). Paste anything from X or
   elsewhere when it asks.
3. Carry on down the list below. Each skill tells you what to run next.

## The eleven

| command | job | what it does |
| --- | --- | --- |
| `/validate-idea` | Intake | Your idea, who it is for, the search terms, and the pass/fail bar, locked before any data comes in. Moving it later is recorded. |
| `/validate-mine` | Complaint Miner | Up to 1,000 posts from Reddit (through the PullPush archive), Hacker News and App Store reviews, plus anything you paste (X, Discord, G2). Deduped, every one with a link. |
| `/validate-cluster` | Pain Mapper | Sub-agents label every post against one shared codebook: is it a complaint, which pain, who is speaking, what they tried. Every quote is checked against the post. |
| `/validate-pain` | Pain Index | Scores each pain out of 100 with published weights. Money talk weighs most, then frequency, intensity, workarounds, breadth and recency. |
| `/validate-segment` | Beachhead | Who is complaining, by stated role and by community, and the one group to build for first. |
| `/validate-wtp` | Price Reader | Every price people mention, converted to a monthly figure and sorted into would pay, already pay and too expensive. A range only when there are enough prices. |
| `/validate-competitors` | Competitor Gaps | Mines each competitor's own users with the same codebook, then maps where they still hurt. |
| `/validate-prospects` | Prospect List | The people who described the pain in public, one row each, with their own words and a link. For interviews. |
| `/validate-interview` | Interview Kit | A Mom Test script about the past, and one honest, personal draft per prospect. You send them. |
| `/validate-smoke` | Smoke Test | Landing page copy in plain words, where to share it, and the numbers that count as a pass, fixed in advance. |
| `/validate-verdict` | The Trial | Prosecution, defense and judge sub-agents. Claims that cite nothing real are struck. The ruling has to fit your bar. |

## How to use it

Run them in order. Each one reads what the last one wrote, in a `validator/`
folder in your project.

```
idea -> mine -> cluster -> pain -> segment -> wtp -> competitors -> prospects -> interview -> smoke -> verdict
```

You can stop anywhere. `/validate-verdict` uses whatever has run: with only the
mining, labelling and pain index done, it can still rule, but it can never say
go until a real-world test has passed.

### An example, from a real run

The idea: one inbox for every messaging app, grouped by person, with AI that says
who you owe a reply. Target: professionals who sell or hire through DMs. Bar, set
first: 100 complaints and 10 money signals in the data, then 200 waitlist signups
and 10 refundable preorders in the real world.

1. **`/validate-mine`** with eight pain phrases ("too many apps" messages,
   "forgot to reply" clients...). 557 posts from Reddit, Hacker News and Beeper's
   App Store reviews. PullPush rate-limited the subreddit searches; the run says so
   in `sources.md` and carries on.
2. **`/validate-cluster`**: 12 labelling sub-agents. 557 posts became 235 relevant
   and 113 real complaints, every quote checked.
3. **`/validate-pain`**: missed or forgotten messages scored highest (64),
   then too many apps (49) and existing tools that break (46, but 61 complaints).
   Complaints passed the bar (113 of 100). Money failed it by one (9 of 10).
4. **`/validate-wtp`**: no range. The only buyer price came from one person: they
   would happily pay £3 a month and find £10 a month not worth it. The tool will
   not invent a range from that.
5. **`/validate-competitors`**: 85% of Beeper's own complaints are about it
   breaking (bans, disconnects, crashes). An open gap, and a warning.
6. **`/validate-prospects`**: 73 people, led by a freelancer whose client email
   "just got buried", a consultancy owner, a recruiter and a makeup artist.
7. **`/validate-verdict`**: 14 claims, none struck. **Narrow**: to freelancers and
   small agencies working client leads across email, LinkedIn and WhatsApp, on
   one pain, leads lost to follow-ups they forgot. Next test: a "who is waiting on
   your reply" page asking for 10 refundable preorders. 83 quotes checked word for
   word. The run ends with `report.md`, a visual `report.html`, and `links.md`
   holding all 627 links it found, sorted by pain theme.

For comparison, the author had researched the same idea by hand from Reddit and X
the day before (those notes are not in this repo). The run found the strongest
pattern (Beeper's real weakness is reliability) with numbers the notes did not
have, and reached the same call: professionals, not consumers. It missed what lived
only on X, because X has no free API and nothing was imported. If your audience is
on X, paste their posts in with `import` before labelling.

## The tools

Plain Python, no dependencies. They are the reason the skills are not just prompts:
every count, score, price and quote comes from a script, not from a model's memory.

| tool | what it does |
| --- | --- |
| `validate-idea/idea.py` | Checks `idea.json` and locks the bar with a digest. `check` fails if the bar moved. |
| `validate-mine/sources.py` | Fetchers for PullPush, HN Algolia and Apple's review feed, plus `import` and `find-app`. Retries, a polite delay, a day-long cache that never stores an outage, and its own relevance filter, because search APIs are fuzzy. |
| `validate-mine/store.py` | One record shape for every source, stable IDs (`R1a2b3c4d`), near-duplicate merging, and `verbatim()`: the word-for-word quote check everything else uses. |
| `validate-cluster/batches.py` | Writes one brief per batch of 50, checks every label file the sub-agents write, and tallies themes. Rejects a batch if one quote is not word for word. |
| `validate-pain/signals.py` | The fixed word rules for money, workaround and intensity signals. |
| `validate-pain/painindex.py` | The 0 to 100 score per theme, the tiers and the check against the bar. Same data and date, same score. |
| `validate-segment/segments.py` | Complaints tabled by role and by community. |
| `validate-wtp/wtp.py` | Reads prices in any common form (`$99/yr`, `₹1,00,000/year`, `10€/month`, `$10-$20/month`) and builds the range. |
| `validate-competitors/gapmap.py` | Your themes against each competitor's complaints: open gap, they struggle too, maybe solved, unclear. |
| `validate-prospects/prospects.py` | The prospect list. Leaves out bots, deleted accounts and anyone on your do-not-contact list. |
| `validate-verdict/trial.py` | Packs the evidence, strikes claims, enforces which rulings the bar allows. |
| `validate-verdict/quotecheck.py` | Checks every quote in every report against its post. |
| `validate-verdict/report.py` | The final `report.md`, a visual `report.html` (one self-contained page, light and dark) and `links.md` (every link the run found, grouped by pain theme). All three are deleted if a single quote fails. |

## The rules that make it honest

- **The bar comes first.** You set what the evidence must show before you see any
  of it. The trial can only rule go if both the evidence and a real-world test
  (signups, preorders) passed.
- **No quote is trusted.** A quote must be three words or more, start and end on
  word edges, and appear in the saved copy of the post it cites (differences in
  spacing and curly quotes aside). It is checked when a sub-agent labels it, again
  before it reaches a report, and once more over every finished report. That proves
  the words were really written. Whether they back a claim is for the trial, and
  you, to judge.
- **No score is a judgement call.** The weights and word rules are in the code,
  with tests. Claude may disagree with a score in words, never change it.
- **Posts are data, never instructions.** Every brief says so, and post text is
  fenced so it cannot pose as part of a brief.

## Fine print

**It reads public posts through public endpoints.** Reddit through the PullPush
archive (a third party, not Reddit), Hacker News through Algolia, App Store reviews
through Apple's public feed. No logins and no browser scraping. Anything else, you
paste in. Those services have their own terms, and checking them for your use is on
you.

**Keep your `validator/` folder private.** It holds people's handles, links and the
full text of their posts, including posts an archive may still hold after the
author deleted them. Add `validator/` to your project's `.gitignore`, never publish
it, and delete it when the validation is over.

**It does not contact anyone, and it does not dig.** The prospect list holds a
handle, a post and a link. The skills refuse to look up anyone's email, employer,
real name or other accounts, or to run contact-finding tools on them. Sending is
yours to do, by hand, a few a day, one message per person, after reading each
platform's and community's rules on messaging people.

**Strangers' words are research, not marketing.** Never use a mined quote as a
testimonial. The smoke test writes copy in plain words, with no fake social
proof.

**Complaints are not demand.** Loud people post. A ranking of pains tells you
where to look, not that anyone will pay. That is what the real-world test is for.

**PullPush is a third-party archive.** It can lag Reddit by a week or two and may
be down. Apple's review feed sometimes comes back empty for a while. The tools
say so instead of guessing.

## Files

```
skills/validate-idea/         SKILL.md, idea.py, idea.example.json
skills/validate-mine/         SKILL.md, sources.py, store.py, netfetch.py, importer.py, minelog.py, mdsafe.py
skills/validate-cluster/      SKILL.md, batches.py, clusterbrief.py, codebook.example.json
skills/validate-pain/         SKILL.md, painindex.py, signals.py
skills/validate-segment/      SKILL.md, segments.py
skills/validate-wtp/          SKILL.md, wtp.py
skills/validate-competitors/  SKILL.md, gapmap.py
skills/validate-prospects/    SKILL.md, prospects.py
skills/validate-interview/    SKILL.md
skills/validate-smoke/        SKILL.md
skills/validate-verdict/      SKILL.md, trial.py, trialpack.py, quotecheck.py, report.py, reporthtml.py, linksmd.py
tests/                        the tests for every tool, all offline
```

## Tests

```bash
python3 -m unittest discover -s tests
```

## Credit

The interview kit follows the ideas in *The Mom Test* by Rob Fitzpatrick, in our
own words. The pack's shape, eleven skills around one outcome, is inspired by Jake
Schincariol's skill packs. Neither is affiliated with this project.

Made by [Sanskar Prajapati](https://theaiadventurer.com).

## License

MIT. See [LICENSE](LICENSE).
