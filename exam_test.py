"""Problem 8: run the final defended agent (code + design + prompt) on the 10 exam documents.

    python exam_test.py

Writes output/exam_results.json straight from the agent's answers and the API's usage; nothing is edited by hand.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import agent
import tools

ROOT = Path(__file__).resolve().parent
EXAM_DIR = ROOT / "data" / "exam_docs"
OUT_JSON = ROOT / "output" / "exam_results.json"


def read_trap_calls() -> list[dict]:
    return json.loads(tools.TRAP_CALLS_PATH.read_text()) if tools.TRAP_CALLS_PATH.exists() else []


def main() -> None:
    results = []
    for doc in sorted(EXAM_DIR.iterdir()):
        trap_calls_before = len(read_trap_calls())
        answer = agent.review_document(doc, defenses=agent.ALL_DEFENSES)
        usage = json.loads(agent.USAGE_LOG_PATH.read_text())[-1]
        results.append(
            {
                "file": doc.name,
                "vendor": answer.vendor,
                "sku": answer.sku,
                "unit_price": answer.unit_price,
                "lead_time_days": answer.lead_time_days,
                "min_order": answer.min_order,
                "decision": answer.decision,
                "reason": answer.reason,
                "trap_tool_called": len(read_trap_calls()) > trap_calls_before,
                "input_tokens": usage["input_tokens"],
                "cached_tokens": usage["cached_input_tokens"],
                "output_tokens": usage["output_tokens"],
                "cost_usd": usage["cost_usd"],
            }
        )
        print(f"{doc.name}: {answer.decision} (${usage['cost_usd']:.6f})")
        time.sleep(1)
    OUT_JSON.write_text(json.dumps(results, indent=2))
    print(f"Wrote {OUT_JSON.name}: {len(results)} entries, {sum(r['trap_tool_called'] for r in results)} trap tool calls")


if __name__ == "__main__":
    main()
