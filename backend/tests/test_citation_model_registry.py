import unittest
from unittest.mock import AsyncMock, patch

from app.ml import citation_model_registry
from app.ml.citation_classifier import inference_text
from app.schemas.score import EvidenceCapsule, Recommendation, ScoreRequest
from app.services.collector import CollectResult
from app.services.extractor import ExtractResult
from app.services.pipeline import Pipeline


class _FakeCitationModel:
    def __init__(self, probability: float) -> None:
        self.probability = probability

    def predict_proba(self, documents):
        return [[1 - self.probability, self.probability] for _ in documents]


class CitationModelRegistryTests(unittest.TestCase):
    def test_assessment_marks_a_high_probability_document_eligible(self) -> None:
        with patch.object(citation_model_registry, "_model", _FakeCitationModel(0.82)), patch.object(
            citation_model_registry, "_meta", {"trained_at": "2026-06-21T00:00:00Z"}
        ):
            assessment = citation_model_registry.assess("task and evidence", 0.60)

        self.assertTrue(assessment.available)
        self.assertTrue(assessment.eligible)
        self.assertEqual(assessment.usable_probability, 0.82)
        self.assertEqual(assessment.model_version, "2026-06-21T00:00:00Z")

    def test_assessment_marks_a_low_probability_document_ineligible(self) -> None:
        with patch.object(citation_model_registry, "_model", _FakeCitationModel(0.28)), patch.object(
            citation_model_registry, "_meta", {"model_type": "test"}
        ):
            assessment = citation_model_registry.assess("task and evidence", 0.60)

        self.assertTrue(assessment.available)
        self.assertFalse(assessment.eligible)
        self.assertEqual(assessment.usable_probability, 0.28)

    def test_inference_text_uses_the_training_field_contract(self) -> None:
        document = inference_text(
            task="Assess a company filing",
            title="Quarterly report",
            url="https://example.com/report",
            author="Ava Patel",
            claims=[{"text": "Revenue increased 10%.", "evidence_snippet": "The filing reports a 10% increase."}],
        )

        self.assertIn("research_task: Assess a company filing", document)
        self.assertIn("claim: Revenue increased 10%.", document)
        self.assertIn("evidence_text: The filing reports a 10% increase.", document)


class _MemoryCache:
    backend = "memory"

    async def get(self, _key):
        return None

    async def set(self, _key, _value):
        return None


class _Collector:
    async def collect(self, url: str) -> CollectResult:
        return CollectResult(
            url=url,
            final_url=url,
            text="The issuer reported 10% revenue growth and linked the full filing.",
            title="Issuer quarterly filing",
            mode="firecrawl",
        )


class _Extractor:
    async def extract(self, _collected, _task: str) -> ExtractResult:
        return ExtractResult(
            claims=[{
                "text": "The issuer reported 10% revenue growth.",
                "supported": True,
                "evidence_snippet": "The full filing states 10% revenue growth.",
                "confidence": 0.9,
            }],
            has_author=True,
            has_citations=True,
            citation_count=4,
            mode="claude",
        )


class CitationGatePipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_low_citation_score_downgrades_an_otherwise_usable_source(self) -> None:
        pipeline = Pipeline(_Collector(), _Extractor(), _MemoryCache())
        with patch(
            "app.services.pipeline.citation_model_registry.assess",
            return_value=citation_model_registry.CitationPrediction(
                available=True,
                usable_probability=0.32,
                threshold=0.50,
                eligible=False,
                model_version="test-model",
            ),
        ), patch(
            "app.services.pipeline.ranker.score",
            return_value=(85, [], [], [], "heuristic"),
        ), patch(
            "app.services.pipeline.compress",
            new=AsyncMock(return_value=EvidenceCapsule(compressed_text="filing evidence")),
        ):
            response = await pipeline.score_source(ScoreRequest(
                url="https://example.com/filing",
                task="Cite revenue growth from the issuer filing",
            ))

        self.assertEqual(response.trust_score, 85)
        self.assertEqual(response.recommendation, Recommendation.CAUTION)
        self.assertFalse(response.citation_assessment.eligible)
        self.assertIn("citation classifier rejected", response.risk_tags)


if __name__ == "__main__":
    unittest.main()
