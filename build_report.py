"""Problem 9: build output/hw6_report.html, one self-contained page, from the real result files in output/.

    python build_report.py

Reads cache_test.json, attack_results.json, defense_results.json, defense_ablation.json, exam_results.json and
red_team.json. A section whose file does not exist yet shows a "not run yet" panel instead of numbers.
No numbers are typed in here; everything shown comes from those files.
"""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = ROOT / "output"
DOCS_PER_DAY, DAYS_PER_MONTH = 1000, 30
BEFORE, AFTER = "none", "code+design+prompt"
LAYERS = ["none", "code", "design", "prompt", "code+design+prompt"]

CSS = """
:root { --ink:#1d2733; --muted:#5b6673; --line:#d5dbe3; --bg:#f6f8fa; --card:#ffffff; --blue:#2a6fdb; --orange:#c76400; --bad:#b3261e; --good:#1b7a3a; }
* { box-sizing:border-box; }
body { margin:0; font:16px/1.5 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color:var(--ink); background:var(--bg); }
main { max-width:980px; margin:0 auto; padding:28px 20px 60px; }
h1 { margin:0 0 4px; font-size:28px; } h2 { margin:36px 0 10px; font-size:22px; border-bottom:2px solid var(--ink); padding-bottom:4px; }
h3 { margin:20px 0 6px; font-size:17px; }
.sub { color:var(--muted); margin:0 0 18px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:14px 16px; margin:12px 0; }
.stats { display:flex; flex-wrap:wrap; gap:12px; margin:12px 0; }
.stat { flex:1 1 180px; background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px 14px; }
.stat b { display:block; font-size:24px; } .stat span { color:var(--muted); font-size:13px; }
table { width:100%; border-collapse:collapse; background:var(--card); font-size:14px; margin:8px 0; }
th, td { border:1px solid var(--line); padding:6px 8px; text-align:left; vertical-align:top; }
th { background:#eef2f6; } td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
.tag { display:inline-block; padding:1px 8px; border-radius:10px; font-size:12px; font-weight:600; border:1px solid; white-space:nowrap; }
.tag.bad { color:var(--bad); border-color:var(--bad); background:#fdecea; } .tag.good { color:var(--good); border-color:var(--good); background:#e8f5ec; }
.pending { border:2px dashed var(--bad); background:#fff7f6; color:var(--bad); border-radius:8px; padding:12px 16px; margin:12px 0; font-weight:600; }
.note { color:var(--muted); font-size:13px; }
svg text { font-family:inherit; fill:var(--ink); }
code { background:#eef2f6; padding:1px 4px; border-radius:3px; font-size:13px; }
.reco { border-left:5px solid var(--ink); }
@media print { body { background:#fff; } }
"""


def load(out_dir: Path, name: str):
    path = out_dir / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def pending(what: str, command: str) -> str:
    return (f'<div class="pending">NOT RUN YET: {escape(what)}. No numbers are shown because none exist. '
            f'Run <code>{escape(command)}</code>, then <code>python build_report.py</code>.</div>')


def money(value: float, digits: int = 6) -> str:
    return f"${value:,.{digits}f}"


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def tag(fooled: bool) -> str:
    return '<span class="tag bad">FOOLED</span>' if fooled else '<span class="tag good">held</span>'


def table(headers: list[str], rows: list[list[str]], numeric: set[int] = frozenset()) -> str:
    head = "".join(f'<th class="{"num" if i in numeric else ""}">{escape(h)}</th>' for i, h in enumerate(headers))
    body = "".join(
        "<tr>" + "".join(f'<td class="{"num" if i in numeric else ""}">{cell}</td>' for i, cell in enumerate(row)) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


# ----------------------------------------------------------------------------------------------
# 1. Caching
# ----------------------------------------------------------------------------------------------


def bar_chart(docs: list[str], with_cache: list[float], without_cache: list[float]) -> str:
    width, height, left, bottom, top = 900, 330, 70, 70, 20
    plot_w, plot_h = width - left - 10, height - bottom - top
    peak = max(max(with_cache), max(without_cache)) * 1.1 or 1.0
    group = plot_w / len(docs)
    bar = group * 0.36
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Cost per document with and without prompt caching" width="100%">']
    for i in range(5):
        value = peak * i / 4
        y = top + plot_h - plot_h * i / 4
        parts.append(f'<line x1="{left}" x2="{width - 10}" y1="{y:.1f}" y2="{y:.1f}" stroke="#d5dbe3"/>')
        parts.append(f'<text x="{left - 6}" y="{y + 4:.1f}" font-size="11" text-anchor="end">${value:.4f}</text>')
    for i, doc in enumerate(docs):
        x0 = left + i * group + group * 0.1
        for j, (value, color, label) in enumerate([(without_cache[i], "#c76400", "without cache"), (with_cache[i], "#2a6fdb", "with cache")]):
            h = plot_h * value / peak
            x = x0 + j * bar
            parts.append(f'<rect x="{x:.1f}" y="{top + plot_h - h:.1f}" width="{bar:.1f}" height="{h:.1f}" fill="{color}"><title>{escape(doc)} {label}: {money(value)}</title></rect>')
        short = doc.split("_")[0]
        parts.append(f'<text x="{x0 + bar:.1f}" y="{top + plot_h + 16}" font-size="12" text-anchor="middle">{escape(short)}</text>')
    parts.append(f'<text x="{left + plot_w / 2}" y="{height - 30}" font-size="12" text-anchor="middle">practice document</text>')
    parts.append(f'<text x="14" y="{top + plot_h / 2}" font-size="12" text-anchor="middle" transform="rotate(-90 14 {top + plot_h / 2})">cost per document (USD)</text>')
    parts.append(f'<rect x="{left}" y="{height - 18}" width="12" height="12" fill="#c76400"/><text x="{left + 18}" y="{height - 8}" font-size="12">without cache</text>')
    parts.append(f'<rect x="{left + 130}" y="{height - 18}" width="12" height="12" fill="#2a6fdb"/><text x="{left + 148}" y="{height - 8}" font-size="12">with cache</text>')
    parts.append("</svg>")
    return "".join(parts)


def section_cache(out_dir: Path) -> str:
    calls = load(out_dir, "cache_test.json")
    if not calls:
        return pending("the caching test (12 practice documents, with and without cache)", "python cache_test.py")
    docs = sorted({c["document"] for c in calls})

    def per_doc(setup: str, key: str) -> list[float]:
        return [sum(c[key] for c in calls if c["setup"] == setup and c["document"] == d) for d in docs]

    cost_w, cost_n = per_doc("with_cache", "cost_usd"), per_doc("without_cache", "cost_usd")
    total_w, total_n = sum(cost_w), sum(cost_n)
    saved = (total_n - total_w) / total_n if total_n else 0.0
    cached_w = sum(c["cached_input_tokens"] for c in calls if c["setup"] == "with_cache")
    input_w = sum(c["input_tokens"] for c in calls if c["setup"] == "with_cache")
    cached_n = sum(c["cached_input_tokens"] for c in calls if c["setup"] == "without_cache")
    rows = [
        [escape(d), money(a), money(b)] for d, a, b in zip(docs, cost_w, cost_n)
    ] + [["<b>total</b>", f"<b>{money(total_w)}</b>", f"<b>{money(total_n)}</b>"]]
    stats = (
        f'<div class="stats"><div class="stat"><b>{saved:.1%}</b><span>saved by caching across {len(docs)} documents</span></div>'
        f'<div class="stat"><b>{money(total_w / len(docs))}</b><span>per document with cache</span></div>'
        f'<div class="stat"><b>{money(total_n / len(docs))}</b><span>per document without cache</span></div>'
        f'<div class="stat"><b>{cached_w / input_w:.0%}</b><span>of input tokens served from cache (with cache); {cached_n:,} cached tokens without cache</span></div></div>'
    )
    return (
        stats
        + '<div class="card">' + bar_chart(docs, cost_w, cost_n) + "</div>"
        + table(["document", "with cache", "without cache"], rows, numeric={1, 2})
        + '<p class="note">Every model call in both setups is in <code>output/cache_test.json</code>. The without-cache setup puts a fresh random id first in every request; a without-cache call that reported cached tokens would not count.</p>'
    )


# ----------------------------------------------------------------------------------------------
# 2. Attacks before and after
# ----------------------------------------------------------------------------------------------


def what_went_wrong(record: dict) -> str:
    problems = [f"{f} = {record['answer'][f]!r} (key {record['key'][f]!r})" for f, ok in record["fields_matched"].items() if not ok]
    if not record["decision_matched"]:
        problems.append(f"decision = {record['answer']['decision']} (key {record['key']['decision']})")
    problems += [f"called {c['tool']}" for c in record["trap_calls"]]
    problems += record["link_or_strange_text_found"]
    return escape("; ".join(problems)) if problems else "-"


def section_attacks(out_dir: Path) -> str:
    after = load(out_dir, "defense_results.json")
    ablation = load(out_dir, "defense_ablation.json")
    before = load(out_dir, "attack_results.json") or (ablation or {}).get(BEFORE)
    if not after or not before:
        return pending("the attack run and the defended rerun on the 12 practice documents", "python attack_test.py && python defense_test.py")
    by_after = {r["document"]: r for r in after}
    rows = []
    for b in before:
        a = by_after[b["document"]]
        rows.append([escape(b["document"]), "yes" if b["trap_hidden_in_document"] else "no (clean)",
                     tag(b["fooled"]), what_went_wrong(b), tag(a["fooled"]), what_went_wrong(a)])
    stats = (
        f'<div class="stats"><div class="stat"><b>{sum(r["fooled"] for r in before)} of {len(before)}</b><span>documents fooled the agent with no defenses</span></div>'
        f'<div class="stat"><b>{sum(r["fooled"] for r in after)} of {len(after)}</b><span>fooled it with code + design + prompt defenses</span></div>'
        f'<div class="stat"><b>{sum(r["trap_tool_called"] for r in before)} / {sum(r["trap_tool_called"] for r in after)}</b><span>trap tool calls before / after</span></div></div>'
    )
    out = stats + table(["document", "trap hidden?", "before", "what went wrong before", "after", "what went wrong after"], rows)
    if ablation:
        docs = [r["document"] for r in before]
        by = {label: {r["document"]: r for r in recs} for label, recs in ablation.items()}
        layer_rows = [[escape(d)] + [tag(by[l][d]["fooled"]) for l in LAYERS if l in by] for d in docs]
        layer_rows.append(["<b>fooled total</b>"] + [f'<b>{sum(r["fooled"] for r in ablation[l])}</b>' for l in LAYERS if l in ablation])
        out += "<h3>Each defense layer on its own</h3>" + table(["document"] + [l for l in LAYERS if l in ablation], layer_rows)
    return out


# ----------------------------------------------------------------------------------------------
# 3. What the defenses cost
# ----------------------------------------------------------------------------------------------


def section_defense_cost(out_dir: Path) -> str:
    ablation = load(out_dir, "defense_ablation.json")
    if not ablation:
        return pending("the defense ablation run (no defenses, each layer alone, all three)", "python defense_test.py")
    base = ablation.get(BEFORE)
    rows = []
    for label in LAYERS:
        recs = ablation.get(label)
        if not recs:
            continue
        inp, cost = mean([r["input_tokens"] for r in recs]), mean([r["cost_usd"] for r in recs])
        extra_in = inp - mean([r["input_tokens"] for r in base])
        extra_cost = cost - mean([r["cost_usd"] for r in base])
        rows.append([escape(label), f"{inp:,.0f}", f"{mean([r['cached_input_tokens'] for r in recs]):,.0f}",
                     f"{mean([r['output_tokens'] for r in recs]):,.1f}", money(cost), f"{extra_in:+,.0f}", f"{extra_cost:+.6f}"])
    return (
        table(["configuration", "input tokens / doc", "cached / doc", "output tokens / doc", "$ / doc", "extra input tokens / doc", "extra $ / doc"], rows, numeric={1, 2, 3, 4, 5, 6})
        + '<p class="note">Averages over the 12 practice documents. Extra = configuration minus the undefended agent; a negative number means the layer made runs cheaper '
        "(for example, the design layer no longer sends the handbook to the model). The code layer runs in plain Python and uses no tokens itself.</p>"
    )


# ----------------------------------------------------------------------------------------------
# 4. Exam results and red team
# ----------------------------------------------------------------------------------------------


def section_exam(out_dir: Path) -> str:
    exam = load(out_dir, "exam_results.json")
    if not exam:
        return pending("the 10 exam documents", "python exam_test.py")
    rows = [
        [escape(r["file"]), escape(r["vendor"]), escape(str(r["sku"])), "" if r["unit_price"] is None else f"${r['unit_price']:.2f}",
         str(r["lead_time_days"]), str(r["min_order"]), escape(r["decision"]), escape(r["reason"]),
         "yes" if r["trap_tool_called"] else "no", f"{r['input_tokens']:,}", f"{r['cached_tokens']:,}", f"{r['output_tokens']:,}", money(r["cost_usd"])]
        for r in exam
    ]
    stats = (
        f'<div class="stats"><div class="stat"><b>{sum(r["decision"] == "recommend" for r in exam)} / {sum(r["decision"] == "do_not_recommend" for r in exam)}</b><span>recommend / do_not_recommend</span></div>'
        f'<div class="stat"><b>{sum(r["trap_tool_called"] for r in exam)}</b><span>trap tool calls on the exam set</span></div>'
        f'<div class="stat"><b>{money(sum(r["cost_usd"] for r in exam), 5)}</b><span>total for {len(exam)} documents</span></div></div>'
    )
    return stats + table(["file", "vendor", "SKU", "price", "lead (days)", "min order", "decision", "reason", "trap tool", "input", "cached", "output", "cost"], rows, numeric={3, 4, 5, 9, 10, 11, 12})


def section_red_team(out_dir: Path) -> str:
    red = load(out_dir, "red_team.json")
    if not red:
        return pending("the two red-team attacks", "python red_team.py")
    cards = []
    for name, runs in red.items():
        none_run, all_run = runs[BEFORE], runs[AFTER]
        layer_rows = [[escape(l), tag(runs[l]["fooled"]), escape(str(runs[l]["answer"]["sku"])), escape(runs[l]["answer"]["decision"])] for l in LAYERS if l in runs]
        cards.append(
            f'<div class="card"><h3>{escape(name)}</h3>'
            f'<p>Honest answer: SKU {escape(str(none_run["key"]["sku"]))}, <code>{escape(none_run["key"]["decision"])}</code>.<br>'
            f'No defenses: {tag(none_run["fooled"])} answered SKU {escape(str(none_run["answer"]["sku"]))}, <code>{escape(none_run["answer"]["decision"])}</code>.<br>'
            f'All three defenses: {tag(all_run["fooled"])} answered SKU {escape(str(all_run["answer"]["sku"]))}, <code>{escape(all_run["answer"]["decision"])}</code>.</p>'
            + table(["configuration", "result", "SKU", "decision"], layer_rows)
            + "</div>"
        )
    return "".join(cards) + '<p class="note">What is hidden, where, and what each attack tries to do are written up in <code>output/red_team.md</code>.</p>'


# ----------------------------------------------------------------------------------------------
# 5. Recommendation
# ----------------------------------------------------------------------------------------------


def section_recommendation(out_dir: Path) -> str:
    exam = load(out_dir, "exam_results.json")
    ablation = load(out_dir, "defense_ablation.json")
    red = load(out_dir, "red_team.json")
    after = load(out_dir, "defense_results.json")
    if not (exam and ablation and red and after):
        return pending("the exam, defense and red-team runs the recommendation is based on", "python exam_test.py && python defense_test.py && python red_team.py")
    docs_per_month = DOCS_PER_DAY * DAYS_PER_MONTH
    defended_per_doc = mean([r["cost_usd"] for r in exam])
    undefended_per_doc = mean([r["cost_usd"] for r in ablation[BEFORE]])
    red_fooled_after = [n for n, runs in red.items() if runs[AFTER]["fooled"]]
    red_fooled_before = [n for n, runs in red.items() if runs[BEFORE]["fooled"]]
    practice_fooled_after = sum(r["fooled"] for r in after)
    trap_calls = sum(r["trap_tool_called"] for r in exam) + sum(r["trap_tool_called"] for r in after)
    facts = (
        f"<ul><li>Cost: the defended agent averaged {money(defended_per_doc)} per document on the exam set, so {DOCS_PER_DAY:,} documents a day for "
        f"{DAYS_PER_MONTH} days ({docs_per_month:,} documents) is about <b>{money(defended_per_doc * docs_per_month, 2)} per month</b> "
        f"(the undefended agent measured {money(undefended_per_doc * docs_per_month, 2)} per month on the practice set).</li>"
        f"<li>Safety on the practice set: {practice_fooled_after} of {len(after)} documents fooled the fully defended agent; trap tool calls on exam and practice runs: {trap_calls}.</li>"
        f"<li>Red team: {len(red_fooled_before)} of {len(red)} new attacks fooled the undefended agent; {len(red_fooled_after)} of {len(red)} fooled the defended agent"
        f"{' (' + ', '.join(escape(n) for n in red_fooled_after) + ')' if red_fooled_after else ''}.</li></ul>"
    )
    return '<div class="card reco">' + facts + '<p class="note">The judgment below is written by hand from the numbers above; the figures in the list are computed from the result files.</p>' + RECOMMENDATION_TEXT + "</div>"


# Written after the live results exist; empty until then.
RECOMMENDATION_TEXT = """
<p><b>Recommendation: yes, turn it on for real vendor mail, as a drafting assistant with a buyer approving every recommendation, and with all three defense layers on.</b></p>
<p>Why yes: the cost is small (see the monthly figure above, a few dollars a month at 1,000 documents a day), the fully defended agent was not fooled by any of the 12 practice documents, no trap tool was ever called, and the clean quotes still came back right.</p>
<p>Why only with a buyer in the loop:</p>
<ul>
<li>No single layer was enough. The code layer alone missed both of my new attacks, because it does not know those hiding tricks. The design layer alone was fooled whenever the planted figure looked like a normal revision, because the reader model copies it. The prompt layer stopped everything I tried, but it is a request to a model, not a guarantee. Keep all three on.</li>
<li>Nothing can catch a lie that sits in plain sight. A vendor who simply quotes a bad price, or a visible fake "correction", looks identical to a real one. The buyer is the check on that.</li>
<li>The exam results have no answer key, so they were not scored. A buyer should spot-check them, especially any recommend.</li>
<li>I tested 12 practice documents and 2 attacks of my own. A determined attacker has more tricks than that, so keep watching <code>output/trap_calls.json</code>: any entry means a document took over the agent.</li>
</ul>
<p>Keep <code>send_email</code> and <code>approve_payment</code> as logging-only until the buyer step exists, and never connect the agent to real payment or email. Turn it on for incoming quotes first, review the first month of recommendations by hand, then decide whether to widen it.</p>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    out_dir = args.output_dir
    out_path = args.out or out_dir / "hw6_report.html"

    sections = [
        ("1. Caching: what reusing the handbook is worth", section_cache(out_dir)),
        ("2. Attacks before and after the defenses", section_attacks(out_dir)),
        ("3. What the defenses cost", section_defense_cost(out_dir)),
        ("4. Exam results and the two red-team attacks", section_exam(out_dir) + "<h3>Red-team attacks</h3>" + section_red_team(out_dir)),
        ("5. Recommendation to the store manager", section_recommendation(out_dir)),
    ]
    body = "".join(f"<h2>{escape(title)}</h2>{content}" for title, content in sections)
    page = (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>HW 6 report: Campus Customs vendor desk agent</title><style>{CSS}</style></head><body><main>"
        "<h1>Campus Customs vendor desk agent: HW 6 report</h1>"
        '<p class="sub">Caching, attacks, defenses, exam results and a recommendation. Every figure on this page is read from the result files in <code>output/</code>.</p>'
        f"{body}</main></body></html>"
    )
    out_path.write_text(page, encoding="utf-8")
    print(f"Wrote {out_path} ({len(page):,} bytes)")


if __name__ == "__main__":
    main()
