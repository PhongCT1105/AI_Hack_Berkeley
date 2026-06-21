"""Tests for quality gates used by the compression evaluation report."""
from __future__ import annotations

import unittest

from app.services.compression_metrics import quality_metrics, summarize_quality


class CompressionMetricTests(unittest.TestCase):
    def test_structured_outputs_preserve_decision_and_critical_facts(self) -> None:
        raw = (
            '{"citation_decision":"DO_NOT_CITE","claim_supported":false,'
            '"evidence":["SEC filing 18% https://sec.gov"],"rationale":"Vanguard disagrees."}'
        )
        compressed = (
            '{"citation_decision":"DO_NOT_CITE","claim_supported":false,'
            '"evidence":["18% https://sec.gov"],"rationale":"Vanguard disagrees."}'
        )

        metrics = quality_metrics(raw, compressed)

        self.assertTrue(metrics["decision_agreement"])
        self.assertTrue(metrics["reference_json_valid"])
        self.assertTrue(metrics["compressed_json_valid"])
        self.assertEqual(metrics["critical_fact_recall"], 1.0)

    def test_summary_averages_completed_rows(self) -> None:
        quality = quality_metrics('{"citation_decision":"CITE"}', '{"citation_decision":"CITE"}')
        summary = summarize_quality([{"quality": quality}])

        self.assertEqual(summary["completed_queries"], 1)
        self.assertEqual(summary["decision_agreement_rate"], 1.0)
