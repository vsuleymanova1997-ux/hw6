"""Structured types for the vendor desk agent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class VendorDecision(BaseModel):
    """The agent's final answer for one vendor document."""

    vendor: str = Field(description="Vendor name exactly as the document presents it.")
    sku: str | None = Field(description="Campus Customs SKU the quote is for, or null if the document gives none.")
    unit_price: float | None = Field(description="Quoted price per unit in USD, or null if the document does not say.")
    lead_time_days: int | None = Field(description="Lead time in days, or null if the document does not say.")
    min_order: int | None = Field(description="Minimum order in units, or null if the document does not say.")
    decision: Literal["recommend", "do_not_recommend"]
    reason: str = Field(description="One sentence naming the purchasing check that decided it.")


class Extraction(BaseModel):
    """What the quarantined reader model copies out of a document. It carries no decision and no free text."""

    vendor: str = Field(description="Vendor the document is from and branded as (header, signature or sender).")
    sku: str | None = Field(description="Campus Customs SKU the quote is for, or null if the document gives none.")
    unit_price: float | None = Field(description="Quoted price per unit in USD, or null if the document does not say.")
    lead_time_days: int | None = Field(description="Lead time in days, or null if the document does not say.")
    min_order: int | None = Field(description="Minimum order in units, or null if the document does not say.")


class ToolCallRecord(BaseModel):
    name: str
    args: str
    result: str


class AuditEntry(BaseModel):
    """One run of the agent: every tool call plus the final answer."""

    run_id: str
    document: str
    timestamp: str
    tool_calls: list[ToolCallRecord]
    final_answer: VendorDecision
    defenses: str = "none"
    hidden_text_removed: list[str] = []
    extraction: Extraction | None = None


class UsageRecord(BaseModel):
    """Token counts as reported by the API, and what they cost per prices.json."""

    document: str
    timestamp: str
    cache_mode: str
    defenses: str = "none"
    model: str
    requests: int
    input_tokens: int
    cached_input_tokens: int
    cache_write_tokens: int
    output_tokens: int
    cost_usd: float
