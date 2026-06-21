// API client for the Captain America FastAPI engine + a tiny sessionStorage result
// store so the Source Detail screen can read a result by trace_id without refetch.

import { useEffect, useSyncExternalStore } from "react";
import type {
  DemoSource,
  EvalMetrics,
  ResearchResponse,
  ScoreResponse,
} from "./types";
import {
  classifyUrl,
  DEFAULT_DEMO_TASK,
  DEFAULT_DEMO_URLS,
  MOCK_EVAL,
} from "./mock-demo-data";

export { DEFAULT_DEMO_TASK, DEFAULT_DEMO_URLS };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface ScoreHistoryItem {
  received_at: string;
  caller: string;
  request: {
    url: string;
    task: string;
  };
  response: ScoreResponse;
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export async function scoreSource(url: string, task: string): Promise<ScoreResponse> {
  const res = await fetch(`${API_URL}/api/score-source`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Captain-America-Caller": "dashboard",
    },
    body: JSON.stringify({ url, task }),
  });
  return json<ScoreResponse>(res);
}

export async function getResults(): Promise<ScoreHistoryItem[]> {
  return json(await fetch(`${API_URL}/api/results`));
}

export async function getHealth(): Promise<{
  status: string;
  capabilities: Record<string, boolean>;
  cache_backend: string;
}> {
  return json(await fetch(`${API_URL}/api/health`));
}

/** Runs the demo API and falls back to deterministic local results offline. */
export async function runDemo(task: string, urls: string[]): Promise<DemoSource[]> {
  const targets = urls.length ? urls : DEFAULT_DEMO_URLS;
  try {
    const response = await fetch(`${API_URL}/api/demo-run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task, urls: targets }),
    });
    return await json<DemoSource[]>(response);
  } catch {
    return targets.map((url, index) => classifyUrl(url, task, index));
  }
}

/** Returns evaluation metrics with a deterministic fallback for local UI work. */
export async function getEvalMetrics(): Promise<EvalMetrics> {
  try {
    return await json<EvalMetrics>(await fetch(`${API_URL}/api/eval`));
  } catch {
    return MOCK_EVAL;
  }
}

export async function runResearch(prompt: string, maxSources = 20): Promise<ResearchResponse> {
  const response = await fetch(`${API_URL}/api/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Captain-America-Caller": "research-demo" },
    body: JSON.stringify({ prompt, max_sources: maxSources }),
  });
  return json<ResearchResponse>(response);
}

// --- session result store (client-only, via useSyncExternalStore) -------- //
const STORE_KEY = "captain-america:results";
const EMPTY: ScoreResponse[] = [];
const listeners = new Set<() => void>();
let cache: ScoreResponse[] | null = null;
let refreshInFlight: Promise<void> | null = null;

function read(): ScoreResponse[] {
  if (typeof window === "undefined") return EMPTY;
  try {
    return JSON.parse(sessionStorage.getItem(STORE_KEY) ?? "[]");
  } catch {
    return EMPTY;
  }
}

function snapshot(): ScoreResponse[] {
  if (cache === null) cache = read();
  return cache;
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function saveResult(r: ScoreResponse): void {
  if (typeof window === "undefined") return;
  const stamped = { ...r, analyzed_at: new Date().toISOString() };
  cache = [stamped, ...snapshot().filter((x) => x.trace_id !== r.trace_id)];
  sessionStorage.setItem(STORE_KEY, JSON.stringify(cache));
  listeners.forEach((l) => l());
}

export async function refreshResults(): Promise<void> {
  if (typeof window === "undefined") return;
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = getResults()
    .then((items) => {
      const remote = items
        .map((item) => ({
          ...item.response,
          analyzed_at: item.received_at,
          caller: item.caller,
        }))
        .filter((item) => item.trace_id);
      const merged = [
        ...remote,
        ...snapshot().filter((local) => !remote.some((item) => item.trace_id === local.trace_id)),
      ];
      cache = merged;
      sessionStorage.setItem(STORE_KEY, JSON.stringify(cache));
      listeners.forEach((l) => l());
    })
    .catch(() => {
      // The UI remains usable with sessionStorage-only results when the backend is offline.
    })
    .finally(() => {
      refreshInFlight = null;
    });

  return refreshInFlight;
}

/** Subscribe a component to the session result list. */
export function useResults(): ScoreResponse[] {
  useEffect(() => {
    void refreshResults();
  }, []);
  return useSyncExternalStore(subscribe, snapshot, () => EMPTY);
}
