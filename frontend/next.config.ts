import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  /* config options here */
};

export default withSentryConfig(nextConfig, {
  org: "worcester-polytechnic-insti-6p",
  project: "captain-ddoski-frontend",
  // Suppresses source map upload logs unless SENTRY_AUTH_TOKEN is set (CI only).
  silent: true,
});
