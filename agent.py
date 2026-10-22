#!/usr/bin/env python3
"""Campus Customs vendor desk agent entry point.

    python agent.py --doc data/practice_docs/p01_bluehen_quote.html
"""

from __future__ import annotations

import argparse
import json
import os
import re
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.capabilities import ProcessHistory
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RunUsage, UsageLimits

import tools
from models import AuditEntry, Extraction, ToolCallRecord, UsageRecord, VendorDecision

WORKSPACE_ROOT = Path(__file__).resolve().parent
# A .env next to the project wins over one in the folder above it. override=True so a stale
# PORTKEY_API_KEY exported in the shell cannot shadow the .env file.
load_dotenv(WORKSPACE_ROOT.parent / ".env", override=True)
load_dotenv(WORKSPACE_ROOT / ".env", override=True)

PORTKEY_API_KEY = os.getenv("PORTKEY_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-5.6-luna")
BASE_URL = os.getenv("BASE_URL", "https://api.portkey.ai/v1")

PROMPT_PATH = WORKSPACE_ROOT / "prompts" / "prompt.md"
HANDBOOK_PATH = WORKSPACE_ROOT / "data" / "shop_handbook.md"
PRICES_PATH = WORKSPACE_ROOT / "data" / "prices.json"
OUTPUT_DIR = WORKSPACE_ROOT / "output"
USAGE_LOG_PATH = OUTPUT_DIR / "usage_log.json"
AUDIT_TRAIL_PATH = OUTPUT_DIR / "audit_trail.json"

# prices.json is keyed by the model family name used in lecture, not by MODEL_NAME.
PRICE_KEY = "gpt-6-luna"

AUDIT_TEXT_LIMIT = 300
# Normal run: read_document, then the final answer = 2 requests.
RUN_USAGE_LIMITS = UsageLimits(request_limit=6)


NONCE_MARKER = "Request id: "


def _strip_nonce(text: str) -> str:
    # The processed history is stored, so drop the previous request's id before adding a new one.
    return text.split("\n\n", 1)[1] if text.startswith(NONCE_MARKER) else text


def _make_prompt_unique(messages: list[ModelMessage]) -> list[ModelMessage]:
    """Runs before every model request: a fresh random first line changes the very start of the prompt, so no
    earlier request's prefix (even one from this same run) can match and nothing can come from the cache."""
    nonce = f"{NONCE_MARKER}{uuid.uuid4().hex}\n\n"
    patched = []
    for message in messages:
        if isinstance(message, ModelRequest):
            parts = [
                replace(part, content=nonce + _strip_nonce(part.content)) if isinstance(part, SystemPromptPart) else part
                for part in message.parts
            ]
            message = replace(message, parts=parts)
        patched.append(message)
    return patched


@dataclass(frozen=True)
class Defenses:
    """Three independent defense layers. The Problem 3 agent is the all-off setting."""

    code: bool = False  # what the program does to the document before any model sees it
    design: bool = False  # quarantined reader model + the decision made in code
    prompt: bool = False  # security rules in prompts/prompt.md

    @property
    def label(self) -> str:
        names = [name for name in ("code", "design", "prompt") if getattr(self, name)]
        return "+".join(names) if names else "none"

    @staticmethod
    def parse(text: str) -> "Defenses":
        names = {part.strip() for part in text.split(",") if part.strip()}
        if names == {"none"}:
            return Defenses()
        if names == {"all"}:
            return Defenses(True, True, True)
        unknown = names - {"code", "design", "prompt"}
        if unknown:
            raise SystemExit(f"Unknown defense(s): {', '.join(sorted(unknown))}. Use code, design, prompt, all or none.")
        return Defenses(code="code" in names, design="design" in names, prompt="prompt" in names)


NO_DEFENSES = Defenses()
ALL_DEFENSES = Defenses(code=True, design=True, prompt=True)


def prompt_section(name: str) -> str:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    match = re.search(rf"<!-- section:{name} -->\n(.*?)<!-- /section:{name} -->", text, flags=re.S)
    if not match:
        raise SystemExit(f"Section '{name}' not found in {PROMPT_PATH}")
    return match.group(1).strip()


def build_agent(use_cache: bool = True, defenses: Defenses = NO_DEFENSES) -> Agent:
    if not PORTKEY_API_KEY:
        raise SystemExit("PORTKEY_API_KEY was not found in .env (project folder or the folder above it)")
    # Instructions first, handbook second: the whole prefix is identical on every call, so it can be cached.
    if defenses.design:
        # The reader model only copies out facts, so it needs no handbook; the decision is made in code.
        instructions = prompt_section("extract")
    else:
        instructions = prompt_section("task")
    if defenses.prompt:
        instructions += "\n\n" + prompt_section("security")
    system_prompt = instructions
    if not defenses.design:
        system_prompt += "\n\n---\n\n# Campus Customs Shop Handbook\n\n" + HANDBOOK_PATH.read_text(encoding="utf-8")
    # No temperature: gpt-5.6-luna only accepts its default (a temperature of 0 is rejected with a 400).
    settings = ModelSettings()
    capabilities = []
    if use_cache:
        # Same cache key on every call routes them to the same cache.
        settings["openai_prompt_cache_key"] = "campus-customs-vendor-desk"
    else:
        capabilities.append(ProcessHistory(_make_prompt_unique))
    provider = OpenAIProvider(base_url=BASE_URL, api_key=PORTKEY_API_KEY)
    model = OpenAIChatModel(MODEL_NAME, provider=provider)
    agent = Agent(
        model,
        system_prompt=system_prompt,
        output_type=Extraction if defenses.design else VendorDecision,
        model_settings=settings,
        capabilities=capabilities,
    )
    agent.tool_plain(tools.read_document_clean if defenses.code else tools.read_document, name="read_document")
    if not defenses.design:
        # send_email and approve_payment stay defined in tools.py. With the design layer the model that reads
        # documents is never handed them: nothing a document says can reach them.
        agent.tool_plain(tools.send_email)
        agent.tool_plain(tools.approve_payment)
    return agent


def append_to_list(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    existing.append(entry)
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def _shorten(value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    text = " ".join(text.split())
    return text if len(text) <= AUDIT_TEXT_LIMIT else text[: AUDIT_TEXT_LIMIT - 3] + "..."


def build_tool_call_records(messages: list) -> list[ToolCallRecord]:
    results_by_call_id: dict[str, str] = {}
    for message in messages:
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, ToolReturnPart):
                    results_by_call_id[part.tool_call_id] = _shorten(part.content)

    records = []
    for message in messages:
        if isinstance(message, ModelResponse):
            for part in message.parts:
                # final_result is pydantic-ai's output tool; the final answer is logged separately.
                if isinstance(part, ToolCallPart) and part.tool_name != "final_result":
                    records.append(
                        ToolCallRecord(
                            name=part.tool_name,
                            args=_shorten(part.args),
                            result=results_by_call_id.get(part.tool_call_id, ""),
                        )
                    )
    return records


def compute_cost(usage: RunUsage) -> float:
    prices = json.loads(PRICES_PATH.read_text(encoding="utf-8"))[PRICE_KEY]
    # input_tokens already includes the cached tokens, so bill the rest at the normal rate.
    uncached = usage.input_tokens - usage.cache_read_tokens - usage.cache_write_tokens
    total = (
        uncached * prices["input_per_1m"]
        + usage.cache_read_tokens * prices["cached_input_per_1m"]
        + usage.cache_write_tokens * prices["cache_write_per_1m"]
        + usage.output_tokens * prices["output_per_1m"]
    )
    return round(total / 1_000_000, 8)


def review_document(document_path: Path, use_cache: bool = True, defenses: Defenses = NO_DEFENSES) -> VendorDecision:
    try:
        relative_path = str(document_path.relative_to(WORKSPACE_ROOT))
    except ValueError:
        raise SystemExit(f"Document must be inside {WORKSPACE_ROOT}")

    tools.reset_removed()
    agent = build_agent(use_cache, defenses)
    prompt = f"Review this vendor document. Its path, for your tool calls, is '{relative_path}'."
    try:
        result = agent.run_sync(prompt, usage_limits=RUN_USAGE_LIMITS)
    except UsageLimitExceeded as error:
        raise SystemExit(f"Stopped after hitting the request limit: {error}") from error

    extraction = result.output if defenses.design else None
    answer = tools.decide(extraction) if defenses.design else result.output

    now = datetime.now(timezone.utc).isoformat()
    usage = result.usage

    usage_record = UsageRecord(
        document=relative_path,
        timestamp=now,
        cache_mode="with_cache" if use_cache else "without_cache",
        defenses=defenses.label,
        model=MODEL_NAME,
        requests=usage.requests,
        input_tokens=usage.input_tokens,
        cached_input_tokens=usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=compute_cost(usage),
    )
    append_to_list(USAGE_LOG_PATH, json.loads(usage_record.model_dump_json()))

    audit_entry = AuditEntry(
        run_id=uuid.uuid4().hex[:12],
        document=relative_path,
        timestamp=now,
        tool_calls=build_tool_call_records(result.all_messages()),
        final_answer=answer,
        defenses=defenses.label,
        hidden_text_removed=list(tools.REMOVED_HIDDEN),
        extraction=extraction,
    )
    append_to_list(AUDIT_TRAIL_PATH, json.loads(audit_entry.model_dump_json()))
    return answer


def main() -> None:
    parser = argparse.ArgumentParser(description="Campus Customs vendor desk agent.")
    parser.add_argument("--doc", required=True, help="Path to one vendor document (.html, .pdf or .eml).")
    parser.add_argument("--no-cache", action="store_true", help="Make the prompt unique so nothing is reused from cache.")
    parser.add_argument(
        "--defenses",
        default="all",
        help="Comma list of defense layers: code, design, prompt; or 'all' (default) or 'none' (the Problem 3 agent).",
    )
    args = parser.parse_args()

    document_path = Path(args.doc).expanduser()
    if not document_path.is_absolute():
        document_path = (Path.cwd() / document_path).resolve()
    if not document_path.exists():
        raise SystemExit(f"Document not found: {document_path}")

    answer = review_document(document_path, use_cache=not args.no_cache, defenses=Defenses.parse(args.defenses))
    print(answer.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
