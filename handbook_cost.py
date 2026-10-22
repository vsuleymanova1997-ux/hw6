"""Problem 2: count the handbook's tokens and price it per call and per 1000 calls."""

import json
from pathlib import Path

import tiktoken

DATA = Path(__file__).resolve().parent / "data"
CALLS = 1000

handbook = (DATA / "shop_handbook.md").read_text(encoding="utf-8")
prices = json.loads((DATA / "prices.json").read_text(encoding="utf-8"))["gpt-6-luna"]

# o200k_base is the tokenizer used by the current OpenAI model family.
tokens = len(tiktoken.get_encoding("o200k_base").encode(handbook))

per_m = 1_000_000
input_rate = prices["input_per_1m"] / per_m
cached_rate = prices["cached_input_per_1m"] / per_m
write_rate = prices["cache_write_per_1m"] / per_m

one_uncached = tokens * input_rate
all_uncached = one_uncached * CALLS
one_cached_read = tokens * cached_rate
first_write = tokens * write_rate
all_cached = first_write + (CALLS - 1) * one_cached_read

print(f"characters: {len(handbook):,}")
print(f"tokens (o200k_base): {tokens:,}")
print()
print(f"1 call, no cache:            {tokens:,} x ${prices['input_per_1m']}/1M = ${one_uncached:.6f}")
print(f"1000 calls, no cache:        ${one_uncached:.6f} x {CALLS} = ${all_uncached:.4f}")
print(f"1 call, cache hit:           {tokens:,} x ${prices['cached_input_per_1m']}/1M = ${one_cached_read:.6f}")
print(f"1st call, cache write:       {tokens:,} x ${prices['cache_write_per_1m']}/1M = ${first_write:.6f}")
print(
    f"1000 calls, with cache:      ${first_write:.6f} + {CALLS - 1} x ${one_cached_read:.6f} = ${all_cached:.4f}"
)
print(f"savings from caching:        ${all_uncached - all_cached:.4f} ({(1 - all_cached / all_uncached):.1%})")
