"""The Token Company integration should be transparent to Anthropic call sites."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from app.core.config import settings
from app.services.llm_clients import create_anthropic_client


class TheTokenCompanyWrapperTests(unittest.TestCase):
    def test_wraps_the_existing_anthropic_client_when_configured(self) -> None:
        base_client = object()
        wrapped_client = object()

        with (
            patch.object(settings, "ttc_api_key", "ttc-test-key"),
            patch("anthropic.AsyncAnthropic", return_value=base_client),
            patch("thetokencompany.anthropic.with_compression", return_value=wrapped_client) as wrap,
        ):
            client = create_anthropic_client()

        self.assertIs(client, wrapped_client)
        self.assertEqual(wrap.call_args.kwargs["compression_api_key"], "ttc-test-key")
        self.assertEqual(wrap.call_args.kwargs["model"], settings.ttc_compression_model)
