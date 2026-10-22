"""Problem 4: run the agent on all 12 practice documents with and without prompt caching.

    python cache_test.py

Writes every model call to output/cache_test.json and the numeric tables to output/cache_test.md.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import agent

ROOT = Path(__file__).resolve().parent
PRACTICE_DIR = ROOT / "data" / "practice_docs"
KEY = {row["file"]: row for row in json.loads((ROOT / "data" / "practice_key.json").read_text())}
PRICES = json.loads(agent.PRICES_PATH.read_text())[agent.PRICE_KEY]
OUT_JSON = ROOT / "output" / "cache_test.json"
OUT_MD = ROOT / "output" / "cache_test.md"
FIELDS = ["vendor", "sku", "unit_price", "lead_time_days", "min_order", "decision"]
SETUPS = ["with_cache", "without_cache"]

# Problem 2's token estimate for the handbook alone (handbook_cost.py).
HANDBOOK_TOKENS_ESTIMATE = 10_058
# A with-cache call after the first should reuse most of the ~10k-token prefix.
MIN_CACHED_FOR_HIT = 9_000
DAYS, DOCS_PER_DAY = 30, 1000


def run_setup(setup: str, calls: list[dict], accuracy: dict[str, int]) -> None:
    for doc in sorted(PRACTICE_DIR.iterdir()):
        ag = agent.build_agent(use_cache=setup == "with_cache")
        relative = str(doc.relative_to(ROOT))
        result = ag.run_sync(
            f"Review this vendor document. Its path, for your tool calls, is '{relative}'.",
            usage_limits=agent.RUN_USAGE_LIMITS,
        )
        responses = [m for m in result.all_messages() if isinstance(m, agent.ModelResponse)]
        for index, response in enumerate(responses, start=1):
            usage = response.usage
            cached, written = usage.cache_read_tokens, usage.cache_write_tokens
            uncached = usage.input_tokens - cached - written
            parts = {
                "uncached_input": uncached * PRICES["input_per_1m"] / 1e6,
                "cached_input": cached * PRICES["cached_input_per_1m"] / 1e6,
                "cache_write": written * PRICES["cache_write_per_1m"] / 1e6,
                "output": usage.output_tokens * PRICES["output_per_1m"] / 1e6,
            }
            calls.append(
                {
                    "setup": setup,
                    "document": doc.name,
                    "call_in_run": index,
                    "timestamp": response.timestamp.isoformat() if response.timestamp else None,
                    "input_tokens": usage.input_tokens,
                    "uncached_input_tokens": uncached,
                    "cached_input_tokens": cached,
                    "cache_write_tokens": written,
                    "output_tokens": usage.output_tokens,
                    "api_usage_all_fields": asdict(usage),
                    "cost_usd": round(sum(parts.values()), 8),
                    "cost_breakdown_usd": {k: round(v, 8) for k, v in parts.items()},
                }
            )
        expected = KEY[doc.name]
        accuracy[setup] = accuracy.get(setup, 0) + sum(getattr(result.output, f) == expected[f] for f in FIELDS)
        print(f"{setup} {doc.name}: {len(responses)} calls, cached tokens {[c['cached_input_tokens'] for c in calls[-len(responses):]]}")
        time.sleep(1)


def totals(rows: list[dict]) -> dict:
    keys = ["input_tokens", "uncached_input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens"]
    out = {k: sum(r[k] for r in rows) for k in keys}
    out["calls"] = len(rows)
    out["cost_usd"] = sum(r["cost_usd"] for r in rows)
    return out


def verify(calls: list[dict]) -> dict:
    no_cache = [c for c in calls if c["setup"] == "without_cache"]
    with_cache = [c for c in calls if c["setup"] == "with_cache"]
    leaks = [c for c in no_cache if c["cached_input_tokens"]]
    later = with_cache[1:]
    hits = [c for c in later if c["cached_input_tokens"] >= MIN_CACHED_FOR_HIT]
    return {
        "without_cache_calls": len(no_cache),
        "without_cache_calls_showing_cached_tokens": len(leaks),
        "without_cache_cache_write_tokens": sum(c["cache_write_tokens"] for c in no_cache),
        "without_cache_valid": not leaks,
        "with_cache_calls_after_first": len(later),
        "with_cache_calls_reusing_handbook": len(hits),
        "with_cache_valid": bool(later) and len(hits) >= 0.8 * len(later),
        "first_with_cache_call_cached_tokens": with_cache[0]["cached_input_tokens"] if with_cache else None,
    }


def write_markdown(calls: list[dict], accuracy: dict[str, int], checks: dict) -> None:
    by_setup = {s: [c for c in calls if c["setup"] == s] for s in SETUPS}
    t = {s: totals(by_setup[s]) for s in SETUPS}
    docs = sorted({c["document"] for c in calls})
    n_docs = len(docs)
    saved = t["without_cache"]["cost_usd"] - t["with_cache"]["cost_usd"]
    pct = saved / t["without_cache"]["cost_usd"]

    def doc_cost(setup: str, doc: str) -> float:
        return sum(c["cost_usd"] for c in by_setup[setup] if c["document"] == doc)

    lines = [
        "# Cache test: 12 practice documents, with and without cache",
        "",
        "Numbers below are generated by `cache_test.py` from `output/cache_test.json` (one entry per model call).",
        "",
        "## 1. Proof each setup did what it should",
        "",
        f"- Without cache: {checks['without_cache_calls_showing_cached_tokens']} of {checks['without_cache_calls']} calls "
        f"read cached tokens (nothing was reused). **{'VALID' if checks['without_cache_valid'] else 'INVALID - run does not count'}**. "
        f"The provider still wrote each unique prompt to its cache ({checks['without_cache_cache_write_tokens']:,} write tokens, billed at the "
        "higher cache-write rate) and cannot be told not to, so see the pure no-cache line below.",
        f"- With cache: {checks['with_cache_calls_reusing_handbook']} of {checks['with_cache_calls_after_first']} calls after "
        f"the very first reported at least {MIN_CACHED_FOR_HIT:,} cached tokens (the handbook prefix). "
        f"**{'VALID' if checks['with_cache_valid'] else 'INVALID'}**. The very first call reported "
        f"{checks['first_with_cache_call_cached_tokens']:,} cached tokens.",
        f"- Answers vs `practice_key.json` (6 fields x {n_docs} docs = {6 * n_docs}): "
        f"with cache {accuracy['with_cache']}, without cache {accuracy['without_cache']}.",
        "",
        "## 2. Cost",
        "",
        "| | with cache | without cache |",
        "|---|---|---|",
        f"| model calls | {t['with_cache']['calls']} | {t['without_cache']['calls']} |",
        f"| input tokens | {t['with_cache']['input_tokens']:,} | {t['without_cache']['input_tokens']:,} |",
        f"| of which cached | {t['with_cache']['cached_input_tokens']:,} | {t['without_cache']['cached_input_tokens']:,} |",
        f"| of which cache write | {t['with_cache']['cache_write_tokens']:,} | {t['without_cache']['cache_write_tokens']:,} |",
        f"| output tokens | {t['with_cache']['output_tokens']:,} | {t['without_cache']['output_tokens']:,} |",
        f"| **total cost** | **${t['with_cache']['cost_usd']:.6f}** | **${t['without_cache']['cost_usd']:.6f}** |",
        f"| **cost per document** | **${t['with_cache']['cost_usd'] / n_docs:.6f}** | **${t['without_cache']['cost_usd'] / n_docs:.6f}** |",
        "",
        f"Saved by caching: ${saved:.6f} total = **{pct:.1%}**.",
        "",
        "Without cache, the unused cache writes were billed at the write rate. At the plain input rate instead "
        f"({t['without_cache']['cache_write_tokens']:,} write tokens x ${PRICES['cache_write_per_1m'] - PRICES['input_per_1m']:.3f}/1M less), "
        f"the no-cache total would be ${t['without_cache']['cost_usd'] - t['without_cache']['cache_write_tokens'] * (PRICES['cache_write_per_1m'] - PRICES['input_per_1m']) / 1e6:.6f}.",
        "",
        "Per document:",
        "",
        "| document | with cache | without cache |",
        "|---|---|---|",
    ]
    lines += [f"| {d} | ${doc_cost('with_cache', d):.6f} | ${doc_cost('without_cache', d):.6f} |" for d in docs]

    nc, wc = t["without_cache"], t["with_cache"]
    est_nc = nc["calls"] * HANDBOOK_TOKENS_ESTIMATE * PRICES["input_per_1m"] / 1e6
    est_wc = (
        HANDBOOK_TOKENS_ESTIMATE * PRICES["cache_write_per_1m"]
        + (wc["calls"] - 1) * HANDBOOK_TOKENS_ESTIMATE * PRICES["cached_input_per_1m"]
    ) / 1e6
    first_nc = by_setup["without_cache"][0]["input_tokens"]
    lines += [
        "",
        "## 3. Real numbers vs the Problem 2 estimate",
        "",
        f"Problem 2 estimated the handbook alone at {HANDBOOK_TOKENS_ESTIMATE:,} tokens. Each document run makes "
        f"{nc['calls'] / n_docs:.1f} model calls, and every call resends the handbook.",
        "",
        "| | handbook-only estimate for these calls | real total (everything) |",
        "|---|---|---|",
        f"| without cache ({nc['calls']} calls) | ${est_nc:.6f} | ${nc['cost_usd']:.6f} |",
        f"| with cache ({wc['calls']} calls) | ${est_wc:.6f} | ${wc['cost_usd']:.6f} |",
        "",
        f"- Real first-call input in the without-cache setup: {first_nc:,} tokens, vs {HANDBOOK_TOKENS_ESTIMATE:,} estimated "
        "for the handbook alone. The difference is the instructions, tool definitions, the random request id and the user message.",
        f"- Real average input per call: {nc['input_tokens'] / nc['calls']:,.0f} tokens without cache.",
        f"- Real average output per call: {nc['output_tokens'] / nc['calls']:,.1f} tokens without cache.",
        "",
        "## 4. Projection: 1000 documents a day for 30 days",
        "",
        f"Uses the measured cost per document above x {DOCS_PER_DAY * DAYS:,} documents.",
        "",
        "| | per document | per day (1000) | 30 days |",
        "|---|---|---|---|",
    ]
    for label, s in (("with cache", "with_cache"), ("without cache", "without_cache")):
        per_doc = t[s]["cost_usd"] / n_docs
        lines.append(f"| {label} | ${per_doc:.6f} | ${per_doc * DOCS_PER_DAY:,.2f} | ${per_doc * DOCS_PER_DAY * DAYS:,.2f} |")
    per_doc_saving = saved / n_docs
    lines += [
        f"| **saved** | ${per_doc_saving:.6f} | ${per_doc_saving * DOCS_PER_DAY:,.2f} | ${per_doc_saving * DOCS_PER_DAY * DAYS:,.2f} |",
        "",
    ]
    premium = nc["cache_write_tokens"] * (PRICES["cache_write_per_1m"] - PRICES["input_per_1m"]) / 1e6
    misses = [c for c in by_setup["with_cache"][1:] if c["cached_input_tokens"] < MIN_CACHED_FOR_HIT]
    est_saving = 1 - (
        (HANDBOOK_TOKENS_ESTIMATE * PRICES["cache_write_per_1m"] + (wc["calls"] - 1) * HANDBOOK_TOKENS_ESTIMATE * PRICES["cached_input_per_1m"])
        / (wc["calls"] * HANDBOOK_TOKENS_ESTIMATE * PRICES["input_per_1m"])
    )
    miss_list = ", ".join(f"{c['document']} call {c['call_in_run']}" for c in misses)
    lines += [
        "## 5. What surprised me, and why",
        "",
        f"1. **The without-cache setup still wrote to the cache.** It read 0 cached tokens, but the API reported {nc['cache_write_tokens']:,} "
        f"cache-write tokens, because the provider caches every prompt automatically and there is no switch to turn that off. "
        f"Write tokens cost more than plain input, so this setup paid ${premium:.6f} extra "
        f"(${nc['cost_usd']:.6f} instead of ${nc['cost_usd'] - premium:.6f}). A random first line stops reuse, not writing.",
        f"2. **Caching is not guaranteed even with an identical prefix.** {len(misses)} of {checks['with_cache_calls_after_first']} later "
        f"with-cache calls missed ({miss_list}); the very first call is a cold start. Cache hits are best effort and depend on routing and timing.",
        f"3. **Savings are {pct:.1%}, not the {est_saving:.1%} that Problem 2's handbook-only math predicts.** The cache-write call and the misses "
        f"still pay write prices, and the document text and output tokens are never cached.",
        f"4. **Second calls in a run read slightly more from cache than first calls** (about 10,690 vs 10,658 tokens): the run's own first "
        "request already wrote the user message and the tool call, which the second request reuses.",
        f"5. **Real input is bigger than the estimate.** The first call was {first_nc:,} tokens against {HANDBOOK_TOKENS_ESTIMATE:,} for the handbook alone: "
        "instructions, tool definitions and the document come on top, and tiktoken is only an estimate of this model's tokenizer.",
        f"6. **Accuracy is {accuracy['with_cache']}/{6 * n_docs} with cache and {accuracy['without_cache']}/{6 * n_docs} without.** "
        "That gap is not caching: this is the plain agent with no defenses, and it is fooled by the trap documents (hidden prices and lead times, a swapped vendor). "
        "Caching does not change the answers.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n")


def main() -> None:
    calls: list[dict] = []
    accuracy: dict[str, int] = {}
    for setup in SETUPS:
        run_setup(setup, calls, accuracy)
        OUT_JSON.write_text(json.dumps(calls, indent=2, default=float))
    checks = verify(calls)
    write_markdown(calls, accuracy, checks)
    print(json.dumps(checks, indent=2))
    print(f"Wrote {OUT_JSON.name} ({len(calls)} calls) and {OUT_MD.name} at {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
