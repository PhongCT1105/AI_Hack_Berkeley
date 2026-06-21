import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.collector import Collector, _result_urls


class CollectorSearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_prefers_firecrawl_search_when_configured(self) -> None:
        collector = Collector()
        collector._search_firecrawl = AsyncMock(return_value=["https://www.sec.gov/edgar"])

        with patch("app.services.collector.settings", SimpleNamespace(has_firecrawl=True)):
            result = await collector.search("SEC filings", 10)

        self.assertEqual(result.urls, ["https://www.sec.gov/edgar"])
        self.assertEqual(result.mode, "firecrawl_search")

    async def test_reports_firecrawl_failure_without_using_another_search_provider(self) -> None:
        collector = Collector()
        collector._search_firecrawl = AsyncMock(side_effect=RuntimeError("provider unavailable"))

        with patch("app.services.collector.settings", SimpleNamespace(has_firecrawl=True)), self.assertLogs(
            "captain_ddoski.collector", level="ERROR"
        ):
            result = await collector.search("SEC filings", 10)

        self.assertEqual(result.urls, [])
        self.assertEqual(result.mode, "firecrawl_search_failed")
        self.assertEqual(result.error, "Firecrawl search request failed")

    async def test_reports_missing_firecrawl_configuration(self) -> None:
        collector = Collector()

        with patch("app.services.collector.settings", SimpleNamespace(has_firecrawl=False)):
            result = await collector.search("SEC filings", 10)

        self.assertEqual(result.urls, [])
        self.assertEqual(result.mode, "firecrawl_search_unavailable")
        self.assertEqual(result.error, "Firecrawl search is not configured")


class SearchResultParserTests(unittest.TestCase):
    def test_firecrawl_result_parser_accepts_url_and_metadata_source_url(self) -> None:
        urls = _result_urls([
            {"url": "https://www.sec.gov/edgar"},
            {"metadata": {"sourceURL": "https://investor.example.com/filing"}},
            {"url": "mailto:bad@example.com"},
            {"url": "https://www.sec.gov/edgar"},
        ], 10)
        self.assertEqual(urls, ["https://www.sec.gov/edgar", "https://investor.example.com/filing"])

if __name__ == "__main__":
    unittest.main()
