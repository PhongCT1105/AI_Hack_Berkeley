import * as Sentry from "@sentry/nextjs";

export async function register() {
  Sentry.init({
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
    tracesSampleRate: 1.0,
    sendDefaultPii: false,
  });
}

export const onRequestError = Sentry.captureRequestError;
