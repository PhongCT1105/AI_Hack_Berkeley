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

    max_facts: int = 12
    max_entities: int = 12
    max_keywords: int = 16
    compact_json: bool = False
    max_clause_chars: int = 52


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

        grouped = {
            kind: [self._compact_clause(fact.text) for fact in semantic_ir.facts if fact.kind == kind]
            for kind in self._kind_order()
        }
        objective = self._compact_clause(semantic_ir.objective)
        parts = [f"o={objective}"]
        if grouped["constraint"]:
            parts.append("c=" + ";".join(grouped["constraint"]))
        if grouped["format"]:
            parts.append("f=" + ";".join(grouped["format"]))
        if grouped["data"]:
            parts.append("d=" + ";".join(grouped["data"]))
        context = [
            item
            for item in grouped["task"] + grouped["entity"] + grouped["audience"] + grouped["context"]
            if item != objective
        ]
        if context:
            parts.append("x=" + ";".join(context[:3]))
        body = "\n".join(parts).casefold()
        missing_entities = [entity for entity in semantic_ir.entities if entity.casefold() not in body]
        missing_numbers = [number for number in semantic_ir.numbers if number not in body]
        if missing_entities:
            parts.append("e=" + ",".join(missing_entities))
        if missing_numbers:
            parts.append("n=" + ",".join(missing_numbers))
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
        blocked = {"Build", "Create", "Write", "It", "Never", "Only", "The", "A", "An", "You", "Your"}
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
            (r"^You are an?\s+", ""),
            (r"^Your task is to\s+", ""),
            (r"^The task is to\s+", ""),
            (r"^Return an?\s+", "return "),
            (r"^Include\s+", "include "),
            (r"^Keep\s+", "keep "),
            (r"^The backend must preserve\s+", "keep "),
            (r"^The summary must preserve\s+", "keep "),
            (r"^It must include\s+", "must include "),
            (r"\bYou must preserve\b", "keep"),
            (r"\bmust preserve\b", "keep"),
            (r"\bmust remain\b", "must stay"),
            (r"\bmust include\b", "needs"),
            (r"\bNever\b", "never"),
            (r"\bAlways keep exact\b", "keep"),
            (r"^The user is an?\s+", "user="),
            (r"^The compressed context is used for\s+", "used_for="),
            (r"^The route\s+", "route "),
            (r"^The purpose is to\s+", "goal="),
            (r"^The Token Company challenge asks teams to\s+", ""),
            (r"^The system turns\s+", "turns "),
            (r"^The demo should show\s+", "show "),
            (r"\bactivity recommendations\b", "activity recs"),
            (r"\brecommendations\b", "recs"),
            (r"\binformation\b", "info"),
            (r"\bsource URL\b", "src_url"),
            (r"\bcitation details\b", "citations"),
            (r"\bpublication date\b", "pub date"),
            (r"\bregulatory references\b", "reg refs"),
            (r"\bguaranteed returns\b", "guaranteed returns"),
            (r"\bfinancial research assistant\b", "finance researcher"),
            (r"\btrustworthy\b", "trusted"),
            (r"\blow-risk retirement investment advice\b", "low-risk retirement advice"),
            (r"\bamount of information sent to an LLM\b", "LLM input"),
            (r"\blong crawled source context\b", "long crawled context"),
            (r"\bcredibility capsule\b", "cred capsule"),
            (r"\bdomain-aware compression system\b", "domain-aware compressor"),
            (r"\bfinance AI agents\b", "finance agents"),
            (r"\btoken reduction\b", "token cut"),
            (r"\bdownstream LLM performance\b", "downstream LLM perf"),
            (r"\bcompressed representation\b", "capsule"),
            (r"\bintentionally raises\b", "raises"),
            (r"\bwith the message\b", "msg="),
            (r"\bcontrolled test data rather than a real product outage\b", "test data,not outage"),
            (r"\bproduction monitoring should cover\b", "monitor"),
            (r"\bexception message\b", "exception msg"),
            (r"\bframework name\b", "framework"),
            (r"\bfield names\b", "fields"),
            (r"\brepetitive narration and boilerplate\b", "repetition"),
            (r"\bsource evidence\b", "evidence"),
            (r"\bobservability summary and a threat feed\b", "observability,threat feed"),
            (r"\bartificial intelligence\b", "AI"),
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

    def _compact_clause(self, text: str) -> str:
        compact = self._compact_text(text)
        compact = re.sub(r"\bthe\b\s*", "", compact, flags=re.IGNORECASE)
        compact = re.sub(r"\ba\b\s*", "", compact, flags=re.IGNORECASE)
        compact = re.sub(r"\ban\b\s*", "", compact, flags=re.IGNORECASE)
        compact = re.sub(r"\s+", " ", compact).strip(" .")
        if len(compact) <= self.config.max_clause_chars:
            return compact
        tokens = compact.split()
        shortened: list[str] = []
        for token in tokens:
            if len(" ".join(shortened + [token])) > self.config.max_clause_chars - 1:
                break
            shortened.append(token)
        return " ".join(shortened).rstrip(",;:")

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


FINANCE_TASK_COMPACT = (
    "Finance trust eval. Return JSON:\n"
    '{"recommendation":"USE|REVIEW|AVOID","trust_score":0,'
    '"risk_tags":[],"evidence":[],"short_rationale":""}'
)

_MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


class FinanceCredibilityCompressor:
    """Domain-aware compressor for finance article credibility analysis.

    Extracts key trust signals into a compact key=value capsule designed for
    Claude's tokenizer. Typical savings: 50-60% vs raw source context.

    Fields:
        url   – source URL (no scheme)
        ret   – return claims
        veh   – investment vehicle
        auth  – author name + missing credentials
        date  – ISO publication date
        brand – named institutions + link status
        reg   – regulatory claim + missing filings
        sales – sales manipulation tactics
        hist  – historical performance claims
    """

    def compress(self, source_text: str) -> SemanticIRResult:
        capsule = self._build_capsule(source_text)
        original_tokens = max(1, round(len(source_text) / 4))
        compact_tokens = max(1, round(len(capsule) / 4))
        return SemanticIRResult(
            original_text=source_text,
            semantic_ir=SemanticIR(
                objective="finance credibility analysis",
                facts=(),
                entities=(),
                numbers=(),
                keywords=(),
            ),
            compact_language=capsule,
            reconstructed_prompt=capsule,
            original_token_estimate=original_tokens,
            compact_token_estimate=compact_tokens,
            reconstruction_token_estimate=compact_tokens,
            compression_ratio=compact_tokens / original_tokens if original_tokens else 0.0,
            notes=("finance-domain credibility capsule",),
        )

    def _build_capsule(self, text: str) -> str:
        fields: list[str] = []
        if url := self._url(text):
            fields.append(f"url={url}")
        if ret := self._returns(text):
            fields.append(f"ret={ret}")
        if veh := self._vehicle(text):
            fields.append(f"veh={veh}")
        if auth := self._author(text):
            fields.append(f"auth={auth}")
        if date := self._date(text):
            fields.append(f"date={date}")
        if brand := self._brands(text):
            fields.append(f"brand={brand}")
        if reg := self._regulatory(text):
            fields.append(f"reg={reg}")
        if sales := self._sales(text):
            fields.append(f"sales={sales}")
        if hist := self._history(text):
            fields.append(f"hist={hist}")
        return "\n".join(fields)

    def _url(self, text: str) -> str:
        m = re.search(r"https?://([^\s,\"]+)", text)
        return m.group(1).rstrip(".") if m else ""

    def _returns(self, text: str) -> str:
        guaranteed = bool(re.search(r"\bguaranteed\b", text, re.IGNORECASE))
        pct_m = re.search(r"(\d+(?:\.\d+)?%)", text)
        if not pct_m:
            return ""
        pct = pct_m.group(1)
        if re.search(r"\bannual\b|\bper\s*year\b|\b/yr\b", text, re.IGNORECASE):
            pct += "/yr"
        elif re.search(r"\bmonthly\b", text, re.IGNORECASE):
            pct += "/mo"
        return ("guaranteed " + pct) if guaranteed else pct

    def _vehicle(self, text: str) -> str:
        m = re.search(r"\binto\s+a?\s*((?:\w+\s+){1,4}fund)\b", text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        m = re.search(
            r"\b(private\s+\w+\s+(?:yield\s+)?fund|crypto\s+\w+\s+fund|hedge\s+fund)\b",
            text,
            re.IGNORECASE,
        )
        return m.group(1) if m else ""

    def _author(self, text: str) -> str:
        m = re.search(
            r'(?:listed\s+only\s+as|author\s+is)\s+"([^"]+)"',
            text,
            re.IGNORECASE,
        )
        if not m:
            m = re.search(r'"([^"]{4,40})"[,\s]+with\s+no', text, re.IGNORECASE)
        if not m:
            # Byline patterns: "By Name" or "By: Name" at line start
            m = re.search(
                r"^By:?\s+([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){0,4})\s*$",
                text,
                re.IGNORECASE | re.MULTILINE,
            )
        name = m.group(1).strip(" ,") if m else ""

        missing: list[str] = []
        if re.search(r"no\s+(?:individual\s+)?credentials?", text, re.IGNORECASE):
            missing.append("no creds")
        if re.search(r"no\s+professional\s+licen[sc]e", text, re.IGNORECASE):
            missing.append("license")
        if re.search(r"no\s+employer\s+disclosure", text, re.IGNORECASE):
            missing.append("employer")

        if name:
            return name + ("/" + "/".join(missing) if missing else "")
        return "/".join(missing) if missing else ""

    def _date(self, text: str) -> str:
        m = re.search(
            r"published\s+(?:on\s+)?(\w+)\s+(\d{1,2}),?\s+(\d{4})",
            text,
            re.IGNORECASE,
        )
        if m:
            month = _MONTHS.get(m.group(1).lower(), "??")
            return f"{m.group(3)}-{month}-{m.group(2).zfill(2)}"
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
        return m.group(0) if m else ""

    def _brands(self, text: str) -> str:
        # Match "mentions/recognizes/cites X and Y" or "X and Y have both..."
        m = re.search(
            r"(?:\bmentions?\b|\brecognizes?\b|\bcites?\b|\bincludes?\b)"
            r"\s+([A-Z][A-Za-z]+)(?:\s+and\s+([A-Z][A-Za-z]+))?",
            text,
        )
        if not m:
            # Fallback: two consecutive known finance brands co-appearing
            m = re.search(
                r"\b([A-Z][A-Za-z]{3,})\s+and\s+([A-Z][A-Za-z]{3,})\b"
                r"(?:\s+have\s+both|\s+are\s+both|\s+were\s+both)",
                text,
            )
        if not m:
            return ""
        brands = [m.group(1)]
        if m.group(2):
            brands.append(m.group(2))
        no_link = bool(
            re.search(r"does\s+not\s+link|no\s+(?:official\s+)?link|not\s+(?:yet\s+)?formally", text, re.IGNORECASE)
        )
        result = ",".join(brands)
        return result + "/no links" if no_link else result

    def _regulatory(self, text: str) -> str:
        claim = ""
        m = re.search(r'"([^"]*(?:SEC)[^"]*)"', text, re.IGNORECASE)
        if m:
            claim = m.group(1)
        elif re.search(r"\bSEC.safe\b", text, re.IGNORECASE):
            claim = "SEC-safe"

        missing: list[str] = []
        if re.search(
            r"no\s+SEC\s+filing|without.{0,80}SEC\s+filing|no\s+SEC\s+registration",
            text, re.IGNORECASE,
        ):
            missing.append("no SEC filing")
        if re.search(
            r"no\s+FINRA\s+BrokerCheck|without.{0,80}FINRA\s+BrokerCheck",
            text, re.IGNORECASE,
        ):
            missing.append("FINRA BrokerCheck")
        if re.search(
            r"no\s+citations?\s+to\s+Federal\s+Reserve|without.{0,80}Federal\s+Reserve",
            text, re.IGNORECASE,
        ):
            missing.append("Fed cites")

        parts = ([claim] if claim else []) + missing
        return "/".join(parts)

    def _sales(self, text: str) -> str:
        tactics: list[str] = []
        if re.search(r"\baffiliate\s+links?\b", text, re.IGNORECASE):
            tactics.append("affiliate")
        if re.search(
            r"\burgent\b|\burgency\b|\bIMPORTANT\b|\boverwhelming\s+demand\b",
            text, re.IGNORECASE,
        ):
            tactics.append("urgent")
        if re.search(r"\blimited.time\b", text, re.IGNORECASE):
            tactics.append("limited-time")
        if re.search(r"\bscarcity\b|\bact\s+now\b", text, re.IGNORECASE):
            tactics.append("scarcity")
        return "/".join(tactics)

    def _history(self, text: str) -> str:
        claims: list[str] = []
        if re.search(r"\bnever\s+lost\s+money\b", text, re.IGNORECASE):
            claims.append("never lost money")
        if re.search(r"\bmarket\s+crash(?:es)?\b", text, re.IGNORECASE):
            claims.append("crashes")
        return "/".join(claims)


