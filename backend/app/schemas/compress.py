"""Schemas for prompt/context compression demos."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


CompressionMethod = Literal["semantic_ir", "sentence_selector"]


class CompressionRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Prompt, source text, or context to compress")
    query: str | None = Field(default=None, description="Task/query the compressed context must support")
    method: CompressionMethod = "semantic_ir"


class CompressionResponse(BaseModel):
    method: CompressionMethod
    original_text: str
    compressed_text: str
    reconstructed_prompt: str | None = None
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    token_savings_percent: int
    preservation_score: float | None = None
    preserved_items: list[str] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    semantic_ir: dict[str, Any] | None = None
    notes: list[str] = Field(default_factory=list)
