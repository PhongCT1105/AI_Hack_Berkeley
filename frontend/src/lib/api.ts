// API client for the AgentShield FastAPI engine + a tiny sessionStorage result
// store so the Source Detail screen can read a result by trace_id without refetch.

import { useSyncExternalStore } from "react";
import type {
  ComparisonPair,
  FeedbackForm,
  ModelStatus,
  ScoreResponse,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, task }),
  });
  return json<ScoreResponse>(res);
}

export async function getHealth(): Promise<{
  status: string;
  capabilities: Record<string, boolean>;
  cache_backend: string;
}> {
  return json(await fetch(`${API_URL}/api/health`));
}

export async function createPair(
  task: string,
  url_a: string,
  url_b: string,
): Promise<ComparisonPair> {
  const res = await fetch(`${API_URL}/api/terac/pairs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task, url_a, url_b }),
  });
  return json<ComparisonPair>(res);
}

export async function nextPair(): Promise<ComparisonPair | null> {
  return json(await fetch(`${API_URL}/api/terac/pairs/next`));
}

export async function submitLabel(
  pair_id: string,
  winner: "a" | "b" | "tie",
  checklist: FeedbackForm,
): Promise<{ ok: boolean; label_count: number }> {
  const res = await fetch(`${API_URL}/api/terac/labels`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pair_id, winner, checklist }),
  });
  return json(res);
}

export async function trainModel(): Promise<ModelStatus> {
  return json(await fetch(`${API_URL}/api/terac/train`, { method: "POST" }));
}

export async function getModelStatus(): Promise<ModelStatus> {
  return json(await fetch(`${API_URL}/api/terac/model`));
}

// --- session result store (client-only, via useSyncExternalStore) -------- //
const STORE_KEY = "agentshield:results";
const EMPTY: ScoreResponse[] = [];
const listeners = new Set<() => void>();
let cache: ScoreResponse[] | null = null;

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

/** Subscribe a component to the session result list. */
export function useResults(): ScoreResponse[] {
  return useSyncExternalStore(subscribe, snapshot, () => EMPTY);
}
