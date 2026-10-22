"""Problem 6: run the 12 practice documents with no defenses, each defense layer alone, and all three layers.

    python defense_test.py

Writes output/defense_results.json (all three layers, same shape as attack_results.json plus tokens and dollars),
output/defense_ablation.json (every configuration) and output/defense_results.md.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import agent
import attack_test

ROOT = Path(__file__).resolve().parent
PRACTICE_DIR = ROOT / "data" / "practice_docs"
OUT_DIR = ROOT / "output"
OUT_JSON = OUT_DIR / "defense_results.json"
OUT_ABLATION = OUT_DIR / "defense_ablation.json"
OUT_MD = OUT_DIR / "defense_results.md"

BEFORE = agent.NO_DEFENSES
AFTER = agent.ALL_DEFENSES
SINGLES = [agent.Defenses(code=True), agent.Defenses(design=True), agent.Defenses(prompt=True)]
CONFIGS = [BEFORE, *SINGLES, AFTER]
USAGE_KEYS = ["input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens", "cost_usd"]


def run_config(defenses: agent.Defenses) -> list[dict]:
    records = []
    for doc in sorted(PRACTICE_DIR.iterdir()):
        record = attack_test.score(doc, defenses)
        usage = json.loads(agent.USAGE_LOG_PATH.read_text())[-1]
        audit = json.loads(agent.AUDIT_TRAIL_PATH.read_text())[-1]
        record.update({key: usage[key] for key in USAGE_KEYS})
        record["hidden_text_removed"] = audit["hidden_text_removed"]
        records.append(record)
        print(f"{defenses.label:>20} {doc.name}: fooled={record['fooled']} trap_called={record['trap_tool_called']} ${record['cost_usd']:.6f}")
        time.sleep(1)
    return records


def what_went_wrong(record: dict) -> str:
    problems = [f"{f}={record['answer'][f]!r} (key {record['key'][f]!r})" for f, ok in record["fields_matched"].items() if not ok]
    if not record["decision_matched"]:
        problems.append(f"decision={record['answer']['decision']} (key {record['key']['decision']})")
    problems += [f"called {c['tool']}" for c in record["trap_calls"]]
    problems += record["link_or_strange_text_found"]
    return "; ".join(problems) if problems else "-"


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def write_markdown(results: dict[str, list[dict]]) -> None:
    before, after = results[BEFORE.label], results[AFTER.label]
    docs = [r["document"] for r in before]
    clean_docs = [r["document"] for r in before if not r["trap_hidden_in_document"]]
    by_doc = {label: {r["document"]: r for r in records} for label, records in results.items()}
    n = len(docs)

    def fooled_count(label: str) -> int:
        return sum(r["fooled"] for r in results[label])

    lines = [
        "# Defense results: three layers, 12 practice documents",
        "",
        f"Before (no defenses = the Problem 3 agent): fooled on {fooled_count(BEFORE.label)} of {n} documents. "
        f"After (code + design + prompt): fooled on {fooled_count(AFTER.label)} of {n}. "
        f"Trap tools called after: {sum(r['trap_tool_called'] for r in after)}. "
        f"Clean documents ({len(clean_docs)}) answered correctly after: "
        f"{sum(not by_doc[AFTER.label][d]['fooled'] for d in clean_docs)} of {len(clean_docs)}.",
        "",
        "## 1. Before and after, all 12 documents",
        "",
        "| document | trap hidden? | before: fooled | before: what went wrong | after: fooled | after: what went wrong |",
        "|---|---|---|---|---|---|",
    ]
    for d in docs:
        b, a = by_doc[BEFORE.label][d], by_doc[AFTER.label][d]
        lines.append(
            f"| {d} | {'yes' if b['trap_hidden_in_document'] else 'no (clean)'} | {'**YES**' if b['fooled'] else 'no'} | "
            f"{what_went_wrong(b)} | {'**YES**' if a['fooled'] else 'no'} | {what_went_wrong(a)} |"
        )

    labels = [c.label for c in CONFIGS]
    lines += [
        "",
        "## 2. Each layer on its own (fooled = YES means the agent failed)",
        "",
        "| document | " + " | ".join(labels) + " |",
        "|---|" + "---|" * len(labels),
    ]
    for d in docs:
        lines.append(f"| {d} | " + " | ".join("**YES**" if by_doc[l][d]["fooled"] else "no" for l in labels) + " |")
    lines.append("| **fooled total** | " + " | ".join(f"**{fooled_count(l)}**" for l in labels) + " |")

    fooled_before = {d for d in docs if by_doc[BEFORE.label][d]["fooled"]}
    caught = {c.label: {d for d in fooled_before if not by_doc[c.label][d]["fooled"]} for c in SINGLES}
    lines += ["", "## 3. What each layer catches that the others miss", ""]
    for c in SINGLES:
        others = set().union(*(caught[o.label] for o in SINGLES if o.label != c.label))
        unique = sorted(caught[c.label] - others)
        lines.append(f"- **{c.label}** alone catches {len(caught[c.label])} of {len(fooled_before)} documents that fooled the undefended agent: "
                     f"{', '.join(sorted(caught[c.label])) or 'none'}. Only this layer catches (neither other layer alone does): "
                     f"{', '.join(unique) or 'none'}.")
    combined_only = sorted(d for d in fooled_before if not any(d in s for s in caught.values()) and not by_doc[AFTER.label][d]["fooled"])
    still = sorted(d for d in docs if by_doc[AFTER.label][d]["fooled"])
    lines += [
        f"- Caught only when the layers work together (no single layer is enough): {', '.join(combined_only) or 'none'}.",
        f"- Still fooled with all three layers: {', '.join(still) or 'none'}.",
        "",
        "How each layer works, and the kind of attack it cannot see:",
        "",
        "- **Code** removes text a person could not see (display:none, zero-size or tiny text, white text, off-page text, HTML comments, "
        "zero-width characters) before any model reads the document. It cannot stop an attack written in ordinary visible text.",
        "- **Design** splits the job: a reader model that has no dangerous tools only copies out five facts, and plain code makes the "
        "recommend / do_not_recommend decision and writes the reason. A document cannot reach send_email or approve_payment, cannot argue "
        "for a decision, and cannot put a link in the answer. It cannot tell whether a number the reader copied was planted.",
        "- **Prompt** tells the model the document is data, to ignore corrections that conflict with the main quote and to keep links out. "
        "It is the only layer that reasons about meaning, but it is a request to a model, not a guarantee.",
    ]

    lines += [
        "",
        "## 4. Extra tokens and dollars per document",
        "",
        f"Averages over the {n} documents. Extra = layer minus the undefended agent. Runs used the normal prompt cache, "
        "so the first document in each configuration pays a cache miss; compare input tokens for a cache-independent view.",
        "",
        "| configuration | input tokens/doc | cached/doc | output tokens/doc | $/doc | extra input tokens/doc | extra $/doc |",
        "|---|---|---|---|---|---|---|",
    ]
    base_in, base_cost = mean([r["input_tokens"] for r in before]), mean([r["cost_usd"] for r in before])
    for label in labels:
        recs = results[label]
        inp, cost = mean([r["input_tokens"] for r in recs]), mean([r["cost_usd"] for r in recs])
        lines.append(
            f"| {label} | {inp:,.0f} | {mean([r['cached_input_tokens'] for r in recs]):,.0f} | "
            f"{mean([r['output_tokens'] for r in recs]):,.1f} | ${cost:.6f} | {inp - base_in:+,.0f} | ${cost - base_cost:+.6f} |"
        )

    lines += [
        "",
        "## 5. Clean documents must still come back right",
        "",
        "| document | after: all fields and decision match | answer |",
        "|---|---|---|",
    ]
    for d in clean_docs:
        a = by_doc[AFTER.label][d]
        ok = all(a["fields_matched"].values()) and a["decision_matched"]
        lines.append(f"| {d} | {ok} | {a['answer']['decision']}: {a['answer']['reason']} |")

    lines += ["", "## 6. Text the code layer removed (all three layers run)", ""]
    for r in after:
        if r["hidden_text_removed"]:
            lines.append(f"- {r['document']}: " + " / ".join(r["hidden_text_removed"]))
    lines.append("")
    OUT_MD.write_text("\n".join(lines) + "\n")


def main() -> None:
    results: dict[str, list[dict]] = {}
    for defenses in CONFIGS:
        results[defenses.label] = run_config(defenses)
        OUT_ABLATION.write_text(json.dumps(results, indent=2))
    OUT_JSON.write_text(json.dumps(results[AFTER.label], indent=2))
    write_markdown(results)
    print(f"Before: {sum(r['fooled'] for r in results[BEFORE.label])} fooled. After: {sum(r['fooled'] for r in results[AFTER.label])} fooled.")


if __name__ == "__main__":
    main()
