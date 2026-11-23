"""report.html: the run's visual report, one self-contained page. Used by report.py.

No scripts, no external files, so it opens anywhere and can be shared as is.
Every piece of text from a post, a label or a sub-agent is escaped, and a quote
appears only if it is word for word in the post it cites.
"""

import html
import os

import store
import quotecheck
from mdsafe import link
from trialpack import read_json

CSS = """
:root { --bg: #f7f7f4; --panel: #ffffff; --fg: #1f2421; --muted: #5d6660; --line: #dfe2dc;
  --accent: #2f6f5e; --accent-soft: #cfe3dc; --ok: #2e7d4f; --warn: #a3650c; --bad: #b3372b; --track: #ecefe9;
  --serif: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
  --sans: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
@media (prefers-color-scheme: dark) { :root { --bg: #151917; --panel: #1d2320; --fg: #e8ebe7; --muted: #a2aba5;
  --line: #313a35; --accent: #7cc4ad; --accent-soft: #2c4a40; --ok: #79c99a; --warn: #e2ae5c; --bad: #f08a7e;
  --track: #2a312d; color-scheme: dark; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 15px/1.55 var(--sans); }
main { max-width: 64rem; margin: 0 auto; padding: 2rem max(16px, env(safe-area-inset-left, 0px)) 4rem;
  display: flex; flex-direction: column; gap: 2rem; }
h1 { font: 400 2rem/1.2 var(--serif); margin: 0; text-wrap: balance; }
h1.long { font-size: 1.35rem; line-height: 1.35; }
h2 { font-size: 1.15rem; font-weight: 600; margin: 0 0 .25rem; }
h3 { font-size: 1rem; font-weight: 600; margin: 0; line-height: 1.45; }
p { margin: 0; max-width: 68ch; }
.muted { color: var(--muted); }
.small { font-size: .85rem; }
.label { font-size: .75rem; letter-spacing: .05em; text-transform: uppercase; color: var(--muted); }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 19rem), 1fr)); gap: 1rem; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 1.1rem 1.2rem;
  display: flex; flex-direction: column; gap: .6rem; min-width: 0; }
.ruling { font: 400 2.2rem/1.1 var(--serif); text-transform: capitalize; color: var(--accent); }
.tablewrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: .85rem; font-variant-numeric: tabular-nums; }
th { text-align: left; color: var(--muted); font-weight: 600; border-bottom: 1px solid var(--line); padding: .35rem .5rem; }
td { border-bottom: 1px solid var(--line); padding: .35rem .5rem; vertical-align: top; }
td.n, th.n { text-align: right; }
.pill { display: inline-block; border: 1px solid currentColor; border-radius: 999px; padding: 0 .55rem; font-size: .75rem; white-space: nowrap; }
.ok { color: var(--ok); } .warn { color: var(--warn); } .bad { color: var(--bad); }
.bars { display: flex; flex-direction: column; gap: .45rem; }
.bar { display: grid; grid-template-columns: minmax(7rem, 38%) 1fr; gap: .6rem; align-items: center; font-size: .85rem; }
.bar .name { overflow-wrap: anywhere; }
.track { background: var(--track); border-radius: 4px; height: 1.3rem; position: relative; }
.fill { background: var(--accent); border-radius: 4px; height: 100%; min-width: 2px; }
.fill.muted { background: var(--muted); opacity: .45; }
.fill.inner { position: absolute; left: 0; top: 0; background: var(--accent); }
.value { position: absolute; left: .4rem; top: 50%; transform: translateY(-50%); font-size: .75rem; color: var(--fg); white-space: nowrap; }
.claims { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: .55rem; }
.claim { display: grid; grid-template-columns: 2.4rem 1fr; gap: .5rem; font-size: .85rem; }
.tag { border-radius: 5px; text-align: center; font-size: .75rem; padding: .05rem 0; color: var(--bg); height: fit-content; }
.tag.prosecution { background: var(--bad); } .tag.defense { background: var(--accent); }
blockquote { margin: .3rem 0 0; padding-left: .6rem; border-left: 2px solid var(--line); }
a { color: var(--accent); }
footer { color: var(--muted); font-size: .8rem; }
"""


def _e(value):
    return html.escape("" if value is None else str(value), quote=True)


def _href(url):
    safe = link(url)
    return ' href="%s" target="_blank" rel="noopener noreferrer"' % _e(safe) if safe else ""


def _pill(text, cls):
    return '<span class="pill %s">%s</span>' % (cls, _e(text))


def _bars(rows, label, value, top=None, end=None, muted=lambda r: False, inner=None):
    top = top or max([value(r) for r in rows] + [1])
    out = ['<div class="bars">']
    for r in rows:
        width = max(0.0, min(100.0, 100.0 * value(r) / top))
        inner_html = ""
        if inner and inner(r):
            inner_html = '<div class="fill inner" style="width:%.1f%%"></div>' % max(0.0, min(100.0, 100.0 * inner(r) / top))
        out.append('<div class="bar"><span class="name">%s</span><div class="track"><div class="fill%s" style="width:%.1f%%">'
                   '</div>%s<span class="value">%s</span></div></div>' % (
                       _e(label(r)), " muted" if muted(r) else "", width, inner_html, _e(end(r) if end else value(r))))
    out.append("</div>")
    return "\n".join(out)


def _verdict(v, idea):
    narrow = '<p class="label">Build for</p><p>%s</p>' % _e(v["narrow_to"]) if v["ruling"] == "narrow" else ""
    return ('<section class="grid"><div class="card"><p class="label">Ruling</p><p class="ruling">%s</p>%s'
            '<p class="label">Next test</p><p>%s</p></div>%s</section>') % (
        _e(v["ruling"]), narrow, _e(v["next_test"]), _bar_card(v, idea))


def _bar_card(v, idea):
    bar, rows = v["bar"], []
    for key, label in (("complaints", "Real complaints"), ("money_signals", "Money signals")):
        r = (bar.get("evidence") or {}).get(key)
        if r:
            rows.append("<tr><td>%s</td><td>Evidence</td><td class=n>%s</td><td class=n>%s</td><td>%s</td></tr>" % (
                label, _e(r["need"]), _e(r["have"]), _pill("pass", "ok") if r["pass"] else _pill("fail", "bad")))
    for item in (idea.get("bar") or {}).get("real_world", []):
        rows.append("<tr><td>%s</td><td>Real world</td><td></td><td></td><td>%s</td></tr>" % (
            _e(item), _pill({True: "pass", False: "fail", None: "not tested"}[bar.get("real_world")], "muted")))
    moves = "".join('<p class="small bad">The bar was moved on %s. Reason given: %s</p>' % (_e(m.get("moved")), _e(m.get("reason")))
                    for m in v.get("bar_moves") or [])
    return ('<div class="card"><h3>The bar, set before any data came in</h3>%s<div class="tablewrap"><table>'
            '<tr><th>Measure</th><th>Part</th><th class=n>Need</th><th class=n>Have</th><th>Result</th></tr>%s'
            '</table></div></div>') % (moves, "".join(rows))


def _funnel(folder):
    t = (read_json(os.path.join(folder, "themes.json"), {}) or {}).get("totals")
    if not t:
        return ""
    rows = [("Posts mined", t.get("in_store", 0)), ("Relevant", t.get("relevant", 0)), ("Real complaints", t.get("complaints", 0))]
    return '<div class="card"><h3>From posts to real complaints</h3>%s</div>' % _bars(
        rows, lambda r: r[0], lambda r: r[1], end=lambda r: "{:,}".format(r[1]))


def _pain(folder):
    pain = read_json(os.path.join(folder, "pain.json"))
    if not pain:
        return ""
    tier = {"worth money": "ok", "real, unproven": "warn"}
    rows = "".join("<tr><td>%s</td><td class=n>%d</td><td class=n>%d</td><td class=n>%d</td><td>%s</td></tr>" % (
        _e(t["name"]), t["metrics"]["complaints"], t["metrics"]["money"], t["score"], _pill(t["tier"], tier.get(t["tier"], "muted")))
        for t in pain["themes"])
    chart = _bars(pain["themes"], lambda t: t["name"], lambda t: t["score"], top=100, end=lambda t: "%d  %s" % (t["score"], t["tier"]),
                  muted=lambda t: t["tier"] not in tier)
    return ('<section><h2>Which pain is worth solving</h2><p class="muted small">Scores out of 100 from fixed rules; money talk '
            'weighs most.</p></section><section class="grid"><div class="card"><h3>Pain score by theme</h3>%s</div>'
            '<div class="card"><div class="tablewrap"><table><tr><th>Theme</th><th class=n>Complaints</th><th class=n>Money'
            '</th><th class=n>Score</th><th>Tier</th></tr>%s</table></div></div></section>') % (chart, rows)


def _gaps_money_who(folder):
    cards = []
    gaps = read_json(os.path.join(folder, "gaps.json"))
    if gaps:
        for slug in sorted(gaps.get("competitors", {})):
            rows = sorted(gaps["themes"], key=lambda t: -t["shares"].get(slug, 0))
            cards.append('<div class="card"><h3>%s: share of its own users\' complaints</h3>%s</div>' % (_e(slug), _bars(
                rows, lambda t: t["name"], lambda t: t["shares"].get(slug, 0), top=1,
                end=lambda t: "%d%%  %s" % (round(100 * t["shares"].get(slug, 0)), t["status"]),
                muted=lambda t: t["status"] != "open gap")))
    wtp = read_json(os.path.join(folder, "wtp.json"))
    if wtp:
        c, r = wtp.get("counts", {}), wtp.get("range") or {}
        price = ("$%.2f to $%.2f a month" % (r["low"], r["high"]) if r.get("low") is not None else "No range: %s." % r.get("note", ""))
        cards.append('<div class="card"><h3>Money</h3><p>%s</p>%s</div>' % (_e(price), _bars(
            [(k.replace("_", " "), c.get(k, 0)) for k in ("would_pay", "pays", "too_expensive", "mention")],
            lambda x: x[0], lambda x: x[1], muted=lambda x: x[0] == "mention")))
    seg = read_json(os.path.join(folder, "segments.json"))
    if seg:
        groups = [("r/" + g["name"], g) for g in seg.get("communities", [])[:6]] + [("role: " + g["name"], g) for g in seg.get("roles", [])[:3]]
        if groups:
            cards.append('<div class="card"><h3>Who is complaining</h3><p class="muted small">Darker part: complaints with money '
                         'talk.</p>%s</div>' % _bars(groups, lambda x: x[0], lambda x: x[1]["complaints"], muted=lambda x: True,
                                                     inner=lambda x: x[1]["money"]))
    return '<section class="grid">%s</section>' % "".join(cards) if cards else ""


def _trial(v, records):
    out = ['<section><h2>The trial</h2><p class="muted small">The judge\'s reasons, each with the claims it rests on. '
           '%d claims kept, %d struck for citing nothing real.</p></section><section class="grid">' % (
               sum(v["kept"].values()), sum(v["struck"].values()))]
    for reason in v["reasons"]:
        items = []
        for c in reason["claims"]:
            quote = ""
            target = c.get("quote_id") or next((e for e in c["evidence"] if e in records), None)
            if c.get("quote") and target in records and quotecheck.quote_matches(c["quote"], records[target]["text"]):
                quote = '<blockquote>&ldquo;%s&rdquo; <a%s>%s</a></blockquote>' % (
                    _e(c["quote"]), _href(records[target]["url"]), _e(target))
            items.append('<li class="claim"><span class="tag %s">%s</span><div>%s <span class="muted">(%s, strength %s)</span>%s</div></li>' % (
                "defense" if c["side"] == "defense" else "prosecution", _e(c["label"]), _e(c["claim"]), _e(c["side"]),
                _e(c["strength"]), quote))
        out.append('<div class="card"><h3>%s</h3><ul class="claims">%s</ul></div>' % (_e(reason["text"]), "".join(items)))
    out.append("</section>")
    return "\n".join(out)


def render_html(folder, verdict, records):
    idea = read_json(os.path.join(folder, "idea.json"), {}) or {}
    stats = store.stats(store.load(os.path.join(folder, store.FILE)))
    title = idea.get("idea") or "Validation report"
    parts = [
        "<!doctype html>", '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
        "<title>Validation report</title><style>%s</style></head><body><main>" % CSS,
        '<header><p class="label">Validation report</p><h1%s>%s</h1><p class="muted small">For: %s</p></header>' % (
            ' class="long"' if len(title) > 70 else "", _e(title), _e(idea.get("target", ""))),
        _verdict(verdict, idea),
        '<section class="grid">%s</section>' % _funnel(folder),
        _pain(folder), _gaps_money_who(folder), _trial(verdict, records),
        '<footer>%s posts mined from %s to %s. Every quote on this page was checked word for word against the post it '
        'cites. Complaints show what hurts, not how many would pay; only a real-world test shows that. Links to every post '
        'are in links.md.</footer>' % ("{:,}".format(stats["total"]), _e(stats["first"]), _e(stats["last"])),
        "</main></body></html>",
    ]
    return "\n".join(p for p in parts if p) + "\n"
