"""Stage 4 — Ranker.

`score_heuristic` is a transparent weighted sum (baseline 50 + signed per-feature
deltas) with ZERO ML dependency — always available. Each delta becomes both a
FeatureContribution (score transparency) and a Verdict (pass/fail per dimension).

When a Terac-trained logistic model is present (model_registry.is_loaded()), its
probability becomes the trust score and scorer_mode flips to "logistic_model";
the heuristic contributions/verdicts are still attached for explainability.
"""
from __future__ import annotations

from app.ml import model_registry
from app.schemas.score import (
    FeatureContribution,
    Recommendation,
    SourceFeatures,
    Verdict,
)
from app.schemas.terac import FeedbackForm

_BASELINE = 50.0


def _clamp(x: float) -> int:
    return int(max(0, min(100, round(x))))


def score_heuristic(f: SourceFeatures) -> tuple[int, list[FeatureContribution], list[Verdict], list[str]]:
    contributions: list[FeatureContribution] = []
    verdicts: list[Verdict] = []
    risk_tags: list[str] = []
    total = _BASELINE

    def add(feature, value, points, dimension, passed, detail, weight):
        nonlocal total
        total += points
        contributions.append(FeatureContribution(feature=feature, value=value, points=round(points, 1)))
        verdicts.append(Verdict(dimension=dimension, passed=passed, detail=detail, weight=weight))

    # Domain reputation (strongest signal)
    if f.domain_listed == "allow":
        add("domain", f.domain_reputation, +25, "domain", True,
            "Recognized high-trust finance/regulatory domain", 25)
    elif f.domain_listed == "block":
        add("domain", f.domain_reputation, -35, "domain", False,
            "Domain on the low-trust finance blocklist", 35)
        risk_tags.append("untrusted domain")
    else:
        delta = (f.domain_reputation - 0.5) * 20
        add("domain", f.domain_reputation, delta, "domain", f.domain_reputation >= 0.5,
            f"Domain reputation {f.domain_reputation:.2f} (neutral prior)", 10)

    # Authorship
    if f.has_author:
        add("has_author", True, +10, "authorship", True, "Named author present", 10)
    else:
        add("has_author", False, -12, "authorship", False, "No identifiable author", 12)
        risk_tags.append("no author")

    # Citations
    if f.has_citations:
        add("has_citations", f.citation_count, +12, "citations", True,
            f"{f.citation_count} citation/reference signals", 12)
    else:
        add("has_citations", f.citation_count, -15, "citations", False,
            "Few or no citations / references", 15)
        risk_tags.append("no citations")

    # HTTPS
    if f.https:
        add("https", True, +3, "transport", True, "Served over HTTPS", 3)
    else:
        add("https", False, -10, "transport", False, "Not served over HTTPS", 10)
        risk_tags.append("insecure transport")

    # Ad density
    if f.ad_density > 0.5:
        add("ad_density", f.ad_density, -15, "ads", False,
            f"High ad/tracker density ({f.ad_density:.2f})", 15)
        risk_tags.append("high ad density")
    elif f.ad_density > 0.2:
        add("ad_density", f.ad_density, -6, "ads", False,
            f"Moderate ad density ({f.ad_density:.2f})", 6)
    else:
        add("ad_density", f.ad_density, +3, "ads", True, "Low ad density", 3)

    # Clickbait
    if f.clickbait_score > 0.6:
        add("clickbait", f.clickbait_score, -20, "framing", False,
            f"Strong clickbait signals ({f.clickbait_score:.2f})", 20)
        risk_tags.append("clickbait title")
    elif f.clickbait_score > 0.3:
        add("clickbait", f.clickbait_score, -8, "framing", False,
            f"Some sensational framing ({f.clickbait_score:.2f})", 8)
    else:
        add("clickbait", f.clickbait_score, +2, "framing", True, "Neutral, non-clickbait framing", 2)

    # Recency
    if f.recency_days is not None:
        if f.recency_days <= 365:
            add("recency_days", f.recency_days, +6, "recency", True,
                f"Recent (~{f.recency_days} days old)", 6)
        elif f.recency_days <= 1095:
            add("recency_days", f.recency_days, 0, "recency", True,
                f"Somewhat dated (~{f.recency_days} days old)", 3)
        else:
            add("recency_days", f.recency_days, -8, "recency", False,
                f"Stale (~{f.recency_days} days old)", 8)
            risk_tags.append("stale content")

    # Thin content
    if f.word_count and f.word_count < 200:
        add("word_count", f.word_count, -6, "depth", False,
            f"Thin content ({f.word_count} words)", 6)
        risk_tags.append("thin content")

    return _clamp(total), contributions, verdicts, risk_tags


def recommend(trust_score: int) -> Recommendation:
    if trust_score >= 70:
        return Recommendation.USE
    if trust_score >= 40:
        return Recommendation.CAUTION
    return Recommendation.AVOID


def confidence(trust_score: int) -> float:
    """0..1 distance from the nearest USE/CAUTION/AVOID decision boundary
    (40, 70). Scorer-mode-agnostic — used by the degradation monitor and
    surfaced as a trace attribute for Arize."""
    return round(min(1.0, min(abs(trust_score - 40), abs(trust_score - 70)) / 30.0), 3)


def score(f: SourceFeatures):
    """Return (trust_score, contributions, verdicts, risk_tags, scorer_mode).

    Heuristic always computed (for explainability). If a trained model is loaded,
    its probability becomes the headline score.
    """
    h_score, contributions, verdicts, risk_tags = score_heuristic(f)
    scorer_mode = "heuristic"
    final = h_score

    if model_registry.is_loaded():
        try:
            prob = model_registry.predict_proba(model_registry.feature_vector(f))
            final = _clamp(prob * 100)
            scorer_mode = "logistic_model"
        except Exception:
            final = h_score  # fall back to heuristic on any predict error

    return final, contributions, verdicts, risk_tags, scorer_mode


def feedback_form_template() -> FeedbackForm:
    """The checklist Terac annotators fill in — kept aligned with verdict dimensions."""
    return FeedbackForm()
