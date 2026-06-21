"""Prompt compression pipeline.

V1 shape:
1. Normalize and deduplicate
2. Query-aware sentence selection
3. Compress the selected text

The final compression stage can use LLMLingua-2 when the optional dependency is
installed. If it is unavailable, the pipeline falls back to the selected text so
callers can still compare the heuristic selection stage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD_RE = re.compile(r"[A-Za-z0-9_']+")
_WHITESPACE_RE = re.compile(r"\s+")

_CONSTRAINT_MARKERS = (
    "must",
    "always",
    "never",
    "only",
    "required",
    "require",
    "constraint",
    "limit",
    "cannot",
    "can't",
    "should",
)


@dataclass(frozen=True)
class CompressionConfig:
    """Tuning knobs for the compression pipeline."""

    short_prompt_word_threshold: int = 120
    max_selected_sentences: int = 8
    target_compression_ratio: float = 0.5
    preserve_numeric_sentences: bool = True
    use_llmlingua2: bool = True
    llmlingua2_model_name: str = "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank"
    llmlingua_device_map: str = "cpu"
    force_tokens: tuple[str, ...] = ("\n", "?", "!", ".", ",")


@dataclass(frozen=True)
class CompressionResult:
    """Structured output for observability and debugging."""

    original_text: str
    normalized_text: str
    selected_text: str
    compressed_text: str
    selected_sentences: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)
    original_word_count: int = 0
    selected_word_count: int = 0
    compressed_word_count: int = 0
    compression_ratio: float = 1.0
    llmlingua_metadata: dict[str, Any] = field(default_factory=dict)


class PromptCompressor:
    """Small, swappable compressor wrapper.

    The heuristic sentence selector stays separate from the compression backend.
    LLMLingua-2 is loaded lazily because its model dependency is relatively
    heavy and may not be installed in every local/dev environment.
    """

    def __init__(self, config: CompressionConfig | None = None) -> None:
        self.config = config or CompressionConfig()
        self._llmlingua: Any | None = None
        self._llmlingua_error: str | None = None

    def compress(self, prompt: str, query: str | None = None) -> CompressionResult:
        normalized_text = self.normalize(prompt)
        original_words = self._word_count(normalized_text)

        if original_words <= self.config.short_prompt_word_threshold:
            return CompressionResult(
                original_text=prompt,
                normalized_text=normalized_text,
                selected_text=normalized_text,
                compressed_text=normalized_text,
                selected_sentences=tuple(self._split_sentences(normalized_text)),
                notes=("skipped: short prompt",),
                original_word_count=original_words,
                selected_word_count=original_words,
                compressed_word_count=original_words,
                compression_ratio=1.0,
            )

        sentences = self._split_sentences(normalized_text)
        deduped_sentences = self._dedupe_sentences(sentences)
        selected_sentences = self._select_sentences(deduped_sentences, query=query)
        selected_text = " ".join(selected_sentences).strip()
        compressed_text, backend_notes, metadata = self._compress_with_llmlingua2(selected_text)

        compressed_words = self._word_count(compressed_text)
        selected_words = self._word_count(selected_text)
        notes = ("pipeline: normalize -> dedupe -> select -> compress",) + backend_notes

        return CompressionResult(
            original_text=prompt,
            normalized_text=normalized_text,
            selected_text=selected_text,
            compressed_text=compressed_text,
            selected_sentences=tuple(selected_sentences),
            notes=notes,
            original_word_count=original_words,
            selected_word_count=selected_words,
            compressed_word_count=compressed_words,
            compression_ratio=compressed_words / original_words if original_words else 0.0,
            llmlingua_metadata=metadata,
        )

    def normalize(self, text: str) -> str:
        """Collapse whitespace and trim the prompt."""

        return _WHITESPACE_RE.sub(" ", text).strip()

    def _split_sentences(self, text: str) -> list[str]:
        sentences = [sentence.strip() for sentence in _SENTENCE_SPLIT_RE.split(text)]
        return [sentence for sentence in sentences if sentence]

    def _dedupe_sentences(self, sentences: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for sentence in sentences:
            key = sentence.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(sentence)
        return deduped

    def _select_sentences(self, sentences: list[str], query: str | None = None) -> list[str]:
        if not sentences:
            return []

        query_terms = set(self._tokenize(query or ""))
        scored_sentences = [
            (self._score_sentence(sentence, query_terms), index, sentence)
            for index, sentence in enumerate(sentences)
        ]
        scored_sentences.sort(key=lambda item: (-item[0], item[1]))

        selected: list[str] = []
        for _, _, sentence in scored_sentences:
            selected.append(sentence)
            if len(selected) >= self.config.max_selected_sentences:
                break

        selected.sort(key=lambda sentence: sentences.index(sentence))
        return selected or sentences[: self.config.max_selected_sentences]

    def _score_sentence(self, sentence: str, query_terms: set[str]) -> float:
        tokens = set(self._tokenize(sentence))
        overlap = len(tokens & query_terms)
        constraint_boost = self._constraint_boost(sentence)
        numeric_boost = 1.0 if self.config.preserve_numeric_sentences and any(char.isdigit() for char in sentence) else 0.0
        length_penalty = min(len(tokens) / 40.0, 1.0)
        return overlap * 2.0 + constraint_boost + numeric_boost - length_penalty

    def _constraint_boost(self, sentence: str) -> float:
        lowered = sentence.casefold()
        if any(marker in lowered for marker in _CONSTRAINT_MARKERS):
            return 1.5
        return 0.0

    def _compress_with_llmlingua2(self, text: str) -> tuple[str, tuple[str, ...], dict[str, Any]]:
        """Compress selected text with LLMLingua-2 when available.

        The official ``llmlingua`` package returns a dictionary containing the
        compressed prompt plus token counts. We keep that raw metadata so the UI
        or CLI can compare LLMLingua-2 against the semantic IR compressor.
        """

        if not self.config.use_llmlingua2:
            return text, ("compression backend: disabled",), {}

        compressor = self._get_llmlingua2()
        if compressor is None:
            reason = self._llmlingua_error or "unknown import/model error"
            return text, (f"compression backend: llmlingua2 unavailable ({reason})",), {}

        try:
            output = compressor.compress_prompt(
                text,
                rate=self.config.target_compression_ratio,
                force_tokens=list(self.config.force_tokens),
            )
        except TypeError:
            output = compressor.compress_prompt(text, rate=self.config.target_compression_ratio)
        except Exception as exc:  # pragma: no cover - depends on optional model runtime
            return text, (f"compression backend: llmlingua2 failed ({exc})",), {}

        if isinstance(output, dict):
            compressed = str(output.get("compressed_prompt") or output.get("compressed_text") or text)
            return compressed, ("compression backend: llmlingua2",), dict(output)

        return str(output), ("compression backend: llmlingua2",), {"raw_output": output}

    def _get_llmlingua2(self) -> Any | None:
        if self._llmlingua is not None:
            return self._llmlingua
        if self._llmlingua_error is not None:
            return None

        try:
            from llmlingua import PromptCompressor as LLMLinguaPromptCompressor

            self._llmlingua = LLMLinguaPromptCompressor(
                model_name=self.config.llmlingua2_model_name,
                device_map=self.config.llmlingua_device_map,
                use_llmlingua2=True,
            )
        except Exception as exc:  # pragma: no cover - optional dependency/model path
            self._llmlingua_error = str(exc)
            return None

        return self._llmlingua

    def _tokenize(self, text: str) -> list[str]:
        return [match.group(0).casefold() for match in _WORD_RE.finditer(text)]

    def _word_count(self, text: str) -> int:
        return len(self._tokenize(text))


