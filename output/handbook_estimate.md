# Handbook size and cost estimate (Problem 2)

`data/shop_handbook.md` is sent to the model on every call. Tokens were counted locally by `handbook_cost.py` with `tiktoken`'s `o200k_base` encoding (the tokenizer family used by current OpenAI models), so this is an estimate rather than the API's own count.

- Size: 28,903 characters = **10,058 tokens**.
- Prices (`data/prices.json`, `gpt-6-luna`, per 1M tokens): input $0.10, cached input $0.01, cache write $0.125, output $0.50.

| Case | Math | Cost |
|---|---|---|
| 1 call, no cache | 10,058 x $0.10 / 1M | $0.001006 |
| 1000 calls, no cache | $0.001006 x 1000 | $1.0058 |
| 1st call, cache write | 10,058 x $0.125 / 1M | $0.001257 |
| each later call, cache hit | 10,058 x $0.01 / 1M | $0.000101 |
| 1000 calls, with cache | $0.001257 + 999 x $0.000101 | $0.1017 |

Caching cuts the handbook's cost over 1000 calls by about 90% ($0.90 saved). The measured numbers from the real runs are in `cache_test.md`.
