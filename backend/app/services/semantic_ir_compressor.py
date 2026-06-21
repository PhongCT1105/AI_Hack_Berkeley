"""Semantic IR prompt compression demo.

Prompt -> Semantic IR -> compact semantic language -> reconstructed prompt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Literal


IRKind = Literal["task", "constraint", "format", "data", "entity", "audience", "context"]

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD_RE = re.compile(r"[A-Za-z0-9_']+")
_WHITESPACE_RE = re.compile(r"\s+")
_NUMBER_RE = re.compile(r"\b\d+(?:[.,:/-]\d+)*%?\b")
_QUOTED_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'')
_ENTITY_RE = re.compile(r"\b(?:[A-Z][A-Za-z0-9_]*)(?:\s+[A-Z][A-Za-z0-9_]*)*\b")

_CONSTRAINT_WORDS = {
    "must", "always", "never", "only", "required", "require", "constraint",
    "limit", "cannot", "can't", "should",
}
_TASK_WORDS = {
    "answer", "build", "classify", "compare", "create", "design", "extract",
    "generate", "implement", "rank", "summarize", "write",
}
_FORMAT_WORDS = {"json", "yaml", "markdown", "table", "csv", "bullets", "list", "schema", "xml"}
_AUDIENCE_WORDS = {"audience", "customer", "developer", "executive", "manager", "student", "user"}
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "is", "it", "of", "on", "or", "that", "the", "this", "to", "with", "you", "your",
}


@dataclass(frozen=True)
class SemanticIRConfig:
    """Tuning knobs for the demo compressor."""

    max_facts: int = 18
    max_entities: int = 12
    max_keywords: int = 16
    compact_json: bool = False


@dataclass(frozen=True)
class SemanticFact:
    """One meaning-bearing unit extracted from the prompt."""

    kind: IRKind
    text: str
    source_index: int
    importance: float
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SemanticIR:
    """Structured representation of the prompt's intent."""

    objective: str
    facts: tuple[SemanticFact, ...]
    entities: tuple[str, ...]
    numbers: tuple[str, ...]
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class SemanticIRResult:
    """End-to-end compression result for demos, debugging, and evaluation."""

    original_text: str
    semantic_ir: SemanticIR
    compact_language: str
    reconstructed_prompt: str
    original_token_estimate: int
    compact_token_estimate: int
    reconstruction_token_estimate: int
    compression_ratio: float
    notes: tuple[str, ...] = field(default_factory=tuple)


class SemanticIRCompressor:
    """Deterministic semantic compression prototype.

    The stages are explicit so a future version can replace the heuristic
    extractor or reconstructor with an LLM while preserving callers.
    """

    def __init__(self, config: SemanticIRConfig | None = None) -> None:
        self.config = config or SemanticIRConfig()

    def compress(self, prompt: str) -> SemanticIRResult:
        normalized = self._normalize(prompt)
        sentences = self._split_sentences(normalized)
        semantic_ir = self.extract_ir(sentences)
        compact_language = self.encode_compact_language(semantic_ir)
        reconstructed_prompt = self.reconstruct_prompt(semantic_ir)

        original_tokens = self._token_estimate(normalized)
        compact_tokens = self._token_estimate(compact_language)
        reconstruction_tokens = self._token_estimate(reconstructed_prompt)

        return SemanticIRResult(
            original_text=prompt,
            semantic_ir=semantic_ir,
            compact_language=compact_language,
            reconstructed_prompt=reconstructed_prompt,
            original_token_estimate=original_tokens,
            compact_token_estimate=compact_tokens,
            reconstruction_token_estimate=reconstruction_tokens,
            compression_ratio=compact_tokens / original_tokens if original_tokens else 0.0,
            notes=(
                "pipeline: prompt -> semantic_ir -> compact_language -> reconstructed_prompt",
                "dependency-free demo; swap extractor/reconstructor later for model calls",
            ),
        )

    def extract_ir(self, sentences: list[str]) -> SemanticIR:
        facts = self._extract_facts(sentences)
        ranked = sorted(facts, key=lambda fact: (-fact.importance, fact.source_index))
        selected = tuple(sorted(ranked[: self.config.max_facts], key=lambda fact: fact.source_index))
        text = " ".join(sentences)

        return SemanticIR(
            objective=self._infer_objective(sentences, selected),
            facts=selected,
            entities=tuple(self._extract_entities(text)[: self.config.max_entities]),
            numbers=tuple(dict.fromkeys(_NUMBER_RE.findall(text))),
            keywords=tuple(self._extract_keywords(text)[: self.config.max_keywords]),
        )

    def encode_compact_language(self, semantic_ir: SemanticIR) -> str:
        """Encode the IR as a compact DSL instead of verbose debug JSON."""

        if self.config.compact_json:
            payload = {
                "o": semantic_ir.objective,
                "e": list(semantic_ir.entities),
                "n": list(semantic_ir.numbers),
                "f": [[self._kind_code(fact.kind), fact.text] for fact in semantic_ir.facts],
            }
            return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))

        grouped = {kind: [self._compact_text(fact.text) for fact in semantic_ir.facts if fact.kind == kind] for kind in self._kind_order()}
        parts = [f"O:{self._compact_text(semantic_ir.objective)}"]
        if grouped["constraint"]:
            parts.append("C:" + " | ".join(grouped["constraint"]))
        if grouped["format"]:
            parts.append("F:" + " | ".join(grouped["format"]))
        if grouped["data"]:
            parts.append("D:" + " | ".join(grouped["data"]))
        context = grouped["entity"] + grouped["audience"] + grouped["context"]
        if context:
            parts.append("X:" + " | ".join(context))
        body = "\n".join(parts).casefold()
        missing_entities = [entity for entity in semantic_ir.entities if entity.casefold() not in body]
        missing_numbers = [number for number in semantic_ir.numbers if number not in body]
        if missing_entities:
            parts.append("E:" + ",".join(missing_entities))
        if missing_numbers:
            parts.append("N:" + ",".join(missing_numbers))
        return "\n".join(parts)

    def reconstruct_prompt(self, semantic_ir: SemanticIR) -> str:
        sections = [f"Objective: {semantic_ir.objective}"]
        grouped = {kind: [fact for fact in semantic_ir.facts if fact.kind == kind] for kind in self._kind_order()}

        tasks = [fact for fact in grouped["task"] if fact.text != semantic_ir.objective]
        if tasks:
            sections.append("Tasks: " + "; ".join(fact.text for fact in tasks))
        if grouped["constraint"]:
            sections.append("Constraints: " + "; ".join(fact.text for fact in grouped["constraint"]))
        if grouped["format"]:
            sections.append("Output format: " + "; ".join(fact.text for fact in grouped["format"]))
        if grouped["data"]:
            sections.append("Important data: " + "; ".join(fact.text for fact in grouped["data"]))

        context = grouped["entity"] + grouped["audience"] + grouped["context"]
        if context:
            sections.append("Context: " + "; ".join(fact.text for fact in context))
        if semantic_ir.entities:
            sections.append("Key entities: " + ", ".join(semantic_ir.entities))
        if semantic_ir.numbers:
            sections.append("Preserve numbers: " + ", ".join(semantic_ir.numbers))

        return "\n".join(sections)

    def _extract_facts(self, sentences: list[str]) -> list[SemanticFact]:
        facts: list[SemanticFact] = []
        seen: set[tuple[IRKind, str]] = set()

        for index, sentence in enumerate(sentences):
            text = self._trim_fact(sentence)
            kind = self._classify_sentence(text)
            key = (kind, text.casefold())
            if not text or key in seen:
                continue
            seen.add(key)
            facts.append(
                SemanticFact(
                    kind=kind,
                    text=text,
                    source_index=index,
                    importance=self._importance(text, kind),
                    tags=tuple(self._tags(text, kind)),
                )
            )

        return facts

    def _classify_sentence(self, sentence: str) -> IRKind:
        tokens = set(self._tokenize(sentence))
        if tokens & _CONSTRAINT_WORDS:
            return "constraint"
        if tokens & _TASK_WORDS:
            return "task"
        if tokens & _FORMAT_WORDS:
            return "format"
        if _NUMBER_RE.search(sentence):
            return "data"
        if tokens & _AUDIENCE_WORDS:
            return "audience"
        if self._extract_entities(sentence):
            return "entity"
        return "context"

    def _infer_objective(self, sentences: list[str], facts: tuple[SemanticFact, ...]) -> str:
        task = next((fact.text for fact in facts if fact.kind == "task"), None)
        if task:
            return task
        if sentences:
            return self._trim_fact(sentences[0])
        return "Respond to the user's prompt"

    def _importance(self, sentence: str, kind: IRKind) -> float:
        base = {
            "constraint": 4.0,
            "task": 3.5,
            "format": 3.0,
            "data": 2.8,
            "audience": 2.2,
            "entity": 2.0,
            "context": 1.0,
        }[kind]
        number_boost = 0.6 if _NUMBER_RE.search(sentence) else 0.0
        entity_boost = min(len(self._extract_entities(sentence)) * 0.25, 0.75)
        length_penalty = min(len(self._tokenize(sentence)) / 80.0, 0.6)
        return base + number_boost + entity_boost - length_penalty

    def _tags(self, sentence: str, kind: IRKind) -> list[str]:
        tags = [kind]
        tokens = set(self._tokenize(sentence))
        if tokens & _CONSTRAINT_WORDS:
            tags.append("preserve")
        if _NUMBER_RE.search(sentence):
            tags.append("number")
        if self._extract_entities(sentence):
            tags.append("entity")
        return list(dict.fromkeys(tags))

    def _extract_entities(self, text: str) -> list[str]:
        quoted = [match.group(1) or match.group(2) for match in _QUOTED_RE.finditer(text)]
        capitalized = _ENTITY_RE.findall(text)
        blocked = {"Build", "Create", "Write", "It", "Never", "Only", "The", "A", "An"}
        entities = [entity.strip() for entity in quoted + capitalized if entity.strip()]
        return [
            entity
            for entity in dict.fromkeys(entities)
            if len(entity) > 1 and entity not in blocked
        ]

    def _extract_keywords(self, text: str) -> list[str]:
        counts: dict[str, int] = {}
        for token in self._tokenize(text):
            if len(token) < 4 or token in _STOPWORDS:
                continue
            counts[token] = counts.get(token, 0) + 1
        return [token for token, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]

    def _compact_text(self, text: str) -> str:
        compact = text.strip()
        replacements = (
            (r"^It must include\s+", "must include "),
            (r"^The user is an?\s+", "user="),
            (r"\bactivity recommendations\b", "activity recs"),
            (r"\brecommendations\b", "recs"),
            (r"\bwith a\b", "w/"),
            (r"\bfor a\b", "for"),
            (r"\bfor an\b", "for"),
            (r",\s+and\s+", ","),
            (r"\s+and\s+", ","),
        )
        for pattern, replacement in replacements:
            compact = re.sub(pattern, replacement, compact, flags=re.IGNORECASE)
        compact = re.sub(r"\s*,\s*", ",", compact)
        compact = re.sub(r"\s+", " ", compact)
        return compact.strip()

    def _kind_code(self, kind: IRKind) -> str:
        return {
            "task": "T",
            "constraint": "C",
            "format": "F",
            "data": "D",
            "entity": "E",
            "audience": "A",
            "context": "X",
        }[kind]

    def _kind_order(self) -> tuple[IRKind, ...]:
        return ("task", "constraint", "format", "data", "entity", "audience", "context")

    def _normalize(self, text: str) -> str:
        return _WHITESPACE_RE.sub(" ", text).strip()

    def _split_sentences(self, text: str) -> list[str]:
        return [sentence.strip() for sentence in _SENTENCE_SPLIT_RE.split(text) if sentence.strip()]

    def _trim_fact(self, sentence: str) -> str:
        sentence = sentence.strip()
        return sentence[:-1] if sentence.endswith(".") else sentence

    def _tokenize(self, text: str) -> list[str]:
        return [match.group(0).casefold() for match in _WORD_RE.finditer(text)]

    def _token_estimate(self, text: str) -> int:
        return max(1, round(len(text) / 4))






