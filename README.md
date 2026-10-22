# HW 6: Campus Customs vendor desk agent

A PydanticAI agent that reads one vendor document (HTML, PDF or .eml), pulls out the vendor, SKU, unit price, lead time and minimum order, and recommends or rejects the quote using the rules in `data/shop_handbook.md`. It has three optional defense layers against documents that try to manipulate it (code, design, prompt) and two trap tools (`send_email`, `approve_payment`) that only log to `output/trap_calls.json`.

## Run the agent

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # then put your own PORTKEY_API_KEY in .env
.venv/bin/python agent.py --doc data/practice_docs/p01_bluehen_quote.html
```

- `--defenses all` (default), `none`, or a list such as `code,design`: which defense layers are on.
- `--no-cache`: make every request's prompt unique so nothing is reused from the prompt cache.
- Each run appends to `output/usage_log.json` (tokens and dollars) and `output/audit_trail.json` (tool calls and the final answer).

The agent reads `PORTKEY_API_KEY` from a `.env` in this folder (or in the folder above it). Never commit the real `.env`.

## Other scripts

| Script | What it does | Writes |
|---|---|---|
| `handbook_cost.py` | token count and cost of the handbook | printed |
| `cache_test.py` | 12 practice documents with and without cache | `output/cache_test.json`, `.md` |
| `attack_test.py` | 12 practice documents, no defenses, scored against the key | `output/attack_results.json`, `.md` |
| `defense_test.py` | no defenses, each layer alone, all three | `output/defense_results.json`, `.md` |
| `make_attacks.py` | writes the two red-team documents in `data/my_attacks/` | `data/my_attacks/` |
| `red_team.py` | the two red-team attacks, undefended and defended | `output/red_team.json`, `.md` |
| `exam_test.py` | the 10 exam documents with the final defended agent | `output/exam_results.json` |
| `build_report.py` | builds the one-file report from the results above | `output/hw6_report.html` |

`AI_prompts.md` has the prompts used for each problem; `output/harness.md` explains the data types, tools and safety layers.
