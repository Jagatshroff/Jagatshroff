---
name: validate-verdict
description: >-
  The Trial. A prosecutor sub-agent argues the idea is dead, a defense sub-agent argues it lives,
  and a judge sub-agent rules go, test, narrow or kill against the bar set in validator/idea.json.
  Any argument that does not cite complaint IDs is struck out, and every quote is checked against
  its source. Compiles the full report. Use when the user asks "should I build this", "go or no
  go", "give me the verdict", "is this idea dead", or "write the validation report".
argument-hint: "[--fresh]"
---

# validate-verdict

The last skill in the pack. Three sub-agents put the idea on trial, using only
the evidence the pack collected. The prosecutor makes the strongest honest
case against it, the defense the strongest case for it. A tool strikes out
every claim that cites nothing real, so the judge only weighs claims that
point at real posts and real numbers. The judge's ruling then has to fit the
bar the user set before seeing any data. You run the trial. You are not the
judge, and you do not overrule it.

What the user typed after `/validate-verdict`: `$ARGUMENTS`

## The tools

```bash
python3 "${CLAUDE_SKILL_DIR}/trial.py" <command>     # pack, save, check, judge, rule
python3 "${CLAUDE_SKILL_DIR}/report.py"              # report.md, report.html and links.md, every quote checked
python3 "${CLAUDE_SKILL_DIR}/quotecheck.py"          # check every quote in every report
```

Below, `TRIAL`, `REPORT` and `QUOTES` mean these three. If the path is not
expanded, use the base directory Claude Code printed for this skill. Each one
takes `--dir validator` first. The trial works in `validator/trial/`.

## Step 1: check what there is

The trial needs at least `pain.json` (`/validate-pain`). It uses every other
output that exists: prices, segments, competitors, interviews, smoke results.
Run `python3 "${CLAUDE_SKILL_DIR}/../validate-idea/idea.py" check validator/idea.json`.
If the bar moved without a recorded reason, stop and tell the user. Recorded
moves go into the report, at the top.

## Step 2: real-world results, if there are any

If the user ran the smoke test or counted interview commitments, write
`validator/realworld.json` with their numbers. Use only numbers the user gave
you or that `smoke.md` records. Never estimate one.

```json
{"results": [
  {"bar": "200 waitlist signups from strangers", "need": 200, "have": 37, "pass": false}
]}
```

Each `bar` is copied exactly from `bar.real_world` in `idea.json`, once. `need`
is the number in that bar, and `pass` must equal `have >= need`: the tool
checks it and refuses a file where they disagree. Leave out anything that was
not tested. The tool then counts the real-world bar as untested.

## Step 3: pack the evidence and run the two sides

```bash
TRIAL pack            # --fresh to throw away an earlier trial, after asking
```

It writes `trial/evidence.md` (the idea, the bar, the scores and an index of
verified quotes), the two briefs, and the rulings the bar allows. Tell the user
the trial is three sub-agent calls. Then send ONE message with two Agent tool
calls, so both sides argue at the same time without seeing each other:

- `subagent_type`: `general-purpose`
- `description`: `trial prosecution` / `trial defense`
- `prompt`: `Read <brief path> and follow it exactly. It is your whole brief.`

If a side printed its JSON instead of writing the file, save it with
`TRIAL save prosecution` (or `defense`) and the reply on stdin.

## Step 4: strike

```bash
TRIAL check
```

Every claim that cites no evidence, an ID that does not exist, a report that
was not in the pack, or a quote that is not word for word is struck. If more
than half of one side's claims were struck, run that side once more from its
brief. Never write, fix or rescue a claim yourself.

## Step 5: the judge

```bash
TRIAL judge
```

It writes the judge's brief: the surviving claims only, labelled P1, P2... and
D1, D2..., the bar, and the rulings allowed:

- **go**: the evidence and the real-world test both passed.
- **test**: the evidence passed, but nothing real has been tested yet.
- **narrow**: build for one group and one pain. Always allowed.
- **kill**: stop. Always allowed, with at least two reasons.

Run one judge sub-agent the same way (`description`: `trial judge`). Then:

```bash
TRIAL rule
```

If the ruling is refused (a ruling the bar does not allow, a reason citing a
struck claim, no `narrow_to`), run the judge once more. Add the refusal reason,
word for word, to its prompt. If it is refused twice, report that the trial did
not reach a valid ruling, and why. Never write the ruling yourself.

## Step 6: the report

```bash
REPORT
```

It writes three files from the same checked data:

- `validator/report.md`: the verdict and the next test first, then the reasons
  with their claims and quotes, the bar, the pain, who, money, competitors,
  coverage, and honest limits.
- `validator/report.html`: the same report as one visual page (bars for the
  funnel, the pain scores, each competitor's gaps, money and who; the trial's
  reasons with checked quotes). Self-contained, light and dark, no scripts:
  it opens in any browser and can be sent as a file.
- `validator/links.md`: every link the run found, grouped by pain theme
  (highest score first), then relevant posts that were not complaints, then
  noise, then each competitor's. No author names.

Then it checks every quote in every report in `validator/` word for word. If
any fails, it removes all three and names the file and line. Fix that file by rerunning the step that wrote it, or
by deleting the bad quote. Never by changing the quote until it matches.

## Step 7: tell the user

1. The verdict in one line, and the next test.
2. The bar: evidence and real world, pass or fail, and any time it was moved.
3. The two or three reasons that decided it, each with one quote and its link,
   as `report.md` gives them.
4. How many claims were struck, from which side.
5. Where to go from here:
   - **go**: build the smallest version for the beachhead. Keep the prospects
     and interviewees close: they are the first users.
   - **test**: `/validate-smoke`, then run this skill again with the results.
   - **narrow**: `/validate-idea` again, for the narrowed group and pain. Moving
     the bar for it needs `idea.py lock --reason`.
   - **kill**: say it plainly. Then point at what the data does support, if
     anything: a theme that scored well, a group that pays.

Do not soften a kill, hedge a go, or add your own opinion of the idea. If you
disagree with the ruling, you may say so once, citing evidence IDs, after
giving the ruling exactly as it is.

## Output

`validator/trial/` (evidence pack, briefs, both sides' claims, the ruling),
`validator/verdict.json`, `validator/report.md`, `validator/report.html`,
`validator/links.md`, and `validator/realworld.json` if real-world results were
given.

Offer to open `report.html` for the user. If this session can publish pages
(an Artifact tool), you may offer to publish it as a private page they can
share; publish only on their yes.

This is the last skill in the pack.
