"use client";

import { useMemo, useState } from "react";
import { ArrowRight, Check, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";

type CompressionMethod = "finance_credibility" | "semantic_ir" | "sentence_selector";

type CompressionResponse = {
  compressed_text: string;
  reconstructed_prompt?: string | null;
  original_tokens: number;
  compressed_tokens: number;
  token_savings_percent: number;
  preservation_score?: number | null;
  preserved_items: string[];
  missing_items: string[];
};

const SAMPLE_CONTEXT =
  "The Token Company challenge asks teams to reduce the amount of information sent to an LLM while preserving the context needed for high-quality outputs. AgentShield should pitch a domain-aware compression system for finance AI agents. The system turns long crawled source context into a credibility capsule that preserves author, citations, dates, claims, risk tags, numbers, and institutions. The demo should show at least 50% token reduction, lower token costs, and no loss in downstream LLM performance on source trust decisions. The compressed representation must remain readable enough for debugging and structured enough for an MCP calling agent.";

const SAMPLE_FACTS =
  "50%,token costs,downstream LLM performance,credibility capsule,finance AI agents";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const LOCAL_API_FALLBACK = "http://localhost:8001";

export default function CompressPage() {
  const [text, setText] = useState(SAMPLE_CONTEXT);
  const [query, setQuery] = useState(SAMPLE_FACTS);
  const [method, setMethod] = useState<CompressionMethod>("finance_credibility");
  const [result, setResult] = useState<CompressionResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const requiredFacts = useMemo(
    () => query.split(",").map((item) => item.trim()).filter(Boolean),
    [query],
  );

  async function runCompression() {
    setLoading(true);
    setError("");
    const apiBases = API_BASE === "http://localhost:8000" ? [API_BASE, LOCAL_API_FALLBACK] : [API_BASE];

    try {
      let lastError = "";
      for (const baseUrl of apiBases) {
        try {
          const response = await fetch(`${baseUrl}/api/compress`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text, query, method }),
          });
          if (!response.ok) throw new Error(`Compression failed with ${response.status}`);
          setResult((await response.json()) as CompressionResponse);
          return;
        } catch (err) {
          lastError = err instanceof Error ? err.message : "Compression failed";
        }
      }
      throw new Error(lastError || "Compression failed");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Compression failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f7f7f4] text-zinc-950">
      <section className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-sm font-medium uppercase tracking-normal text-emerald-700">Token Company challenge</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-normal text-zinc-950 sm:text-4xl">Finance source context to credibility capsule</h1>
              <p className="mt-3 max-w-2xl text-base leading-7 text-zinc-600">Domain-aware compression for finance AI agents, tuned for token savings and preserved source-trust facts.</p>
            </div>
            <div className="flex rounded-lg border border-zinc-200 bg-zinc-50 p-1">
              {(["finance_credibility", "semantic_ir", "sentence_selector"] as CompressionMethod[]).map((item) => (
                <button
                  key={item}
                  className={`h-9 rounded-md px-3 text-sm font-medium ${method === item ? "bg-zinc-950 text-white" : "text-zinc-600 hover:bg-white"}`}
                  onClick={() => setMethod(item)}
                  type="button"
                >
                  {item === "finance_credibility" ? "Finance capsule" : item === "semantic_ir" ? "Semantic IR" : "Sentence selector"}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto grid w-full max-w-7xl gap-5 px-4 py-5 sm:px-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:px-8">
        <div className="grid gap-5">
          <div className="grid gap-4 lg:grid-cols-2">
            <label className="grid gap-2">
              <span className="text-sm font-medium text-zinc-700">Original source context</span>
              <textarea className="min-h-[320px] resize-none rounded-lg border border-zinc-200 bg-white p-4 font-mono text-sm leading-6 outline-none ring-emerald-600/20 focus:ring-4" value={text} onChange={(event) => setText(event.target.value)} />
            </label>
            <div className="grid gap-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-zinc-700">Compressed capsule</span>
                <Button onClick={runCompression} disabled={loading} size="lg">{loading ? <Loader2 className="animate-spin" /> : <ArrowRight />}Compress</Button>
              </div>
              <pre className="min-h-[320px] overflow-auto rounded-lg border border-zinc-200 bg-zinc-950 p-4 font-mono text-sm leading-6 text-zinc-50">{result?.compressed_text || "Capsule pending."}</pre>
            </div>
          </div>

          <label className="grid gap-2">
            <span className="text-sm font-medium text-zinc-700">Required facts</span>
            <input className="h-11 rounded-lg border border-zinc-200 bg-white px-3 text-sm outline-none ring-emerald-600/20 focus:ring-4" value={query} onChange={(event) => setQuery(event.target.value)} />
          </label>

          {result?.reconstructed_prompt ? <div className="grid gap-2"><span className="text-sm font-medium text-zinc-700">Agent reconstruction</span><pre className="max-h-[260px] overflow-auto rounded-lg border border-zinc-200 bg-white p-4 font-mono text-sm leading-6 text-zinc-800">{result.reconstructed_prompt}</pre></div> : null}
          {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
        </div>

        <aside className="grid content-start gap-4">
          <div className="rounded-lg border border-zinc-200 bg-white p-4">
            <p className="text-sm font-medium text-zinc-500">Token savings</p>
            <p className="mt-2 text-4xl font-semibold text-zinc-950">{result ? `${result.token_savings_percent}%` : "--"}</p>
            <div className="mt-4 grid grid-cols-2 gap-3 border-t border-zinc-100 pt-4 text-sm"><Metric label="Original" value={result?.original_tokens ?? 0} /><Metric label="Compressed" value={result?.compressed_tokens ?? 0} /></div>
          </div>
          <div className="rounded-lg border border-zinc-200 bg-white p-4">
            <p className="text-sm font-medium text-zinc-500">Preservation</p>
            <p className="mt-2 text-4xl font-semibold text-zinc-950">{result?.preservation_score != null ? `${Math.round(result.preservation_score * 100)}%` : "--"}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {requiredFacts.map((fact) => {
                const preserved = result?.preserved_items.includes(fact);
                const missing = result?.missing_items.includes(fact);
                return <span key={fact} className={`inline-flex min-h-7 items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium ${preserved ? "border-emerald-200 bg-emerald-50 text-emerald-800" : missing ? "border-red-200 bg-red-50 text-red-700" : "border-zinc-200 bg-zinc-50 text-zinc-600"}`}>{preserved ? <Check className="size-3" /> : null}{fact}</span>;
              })}
            </div>
          </div>
        </aside>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div><p className="text-xs font-medium uppercase tracking-normal text-zinc-500">{label}</p><p className="mt-1 text-2xl font-semibold text-zinc-950">{value || "--"}</p></div>;
}
