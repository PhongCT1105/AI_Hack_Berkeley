"""Regression coverage for the production finance compression path."""
from __future__ import annotations

import unittest

from app.api.compress import compress as compress_api
from app.schemas.compress import CompressionRequest
from app.schemas.score import SourceFeatures
from app.services.capsule import compress as compress_capsule
from app.services.collector import CollectResult
from app.services.extractor import ExtractResult


SOURCE = """
Guaranteed 18% annual return through a private crypto yield fund.
By: Market Insider Team
Published March 14, 2026. The offer has no SEC filing and uses affiliate links.
It has never lost money in market crashes.
"""


class FinanceCredibilityCompressionTests(unittest.IsolatedAsyncioTestCase):
    def test_api_defaults_to_the_finance_compressor(self) -> None:
        result = compress_api(CompressionRequest(text=SOURCE))

        self.assertEqual(result.method, "finance_credibility")
        self.assertIn("ret=guaranteed 18%/yr", result.compressed_text)
        self.assertIn("reg=no SEC filing", result.compressed_text)

    async def test_scoring_capsule_uses_finance_compressor_and_keeps_verdict_context(self) -> None:
        capsule = await compress_capsule(
            CollectResult(
                url="https://best-stock-picks-now.com/double-your-money",
                final_url="https://best-stock-picks-now.com/double-your-money",
                text=SOURCE,
            ),
            ExtractResult(claims=[{"text": "The fund guarantees an 18% annual return.", "supported": False}]),
            SourceFeatures(),
            ["Source has no SEC filing"],
        )

        self.assertEqual(capsule.method, "finance_credibility")
        self.assertIn("url=best-stock-picks-now.com/double-your-money", capsule.compressed_text)
        self.assertIn("claim=The fund guarantees an 18% annual return./unsupported", capsule.compressed_text)
        self.assertIn("reason=Source has no SEC filing", capsule.compressed_text)

