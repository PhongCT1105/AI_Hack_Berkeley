"use client";

import { useState } from "react";
import { Check, Copy, Terminal } from "lucide-react";
import { cn } from "@/lib/utils";
import { ComicPanel } from "./comic-panel";
import { MascotAvatar } from "./mascot-avatar";

// The Render-hosted service predates the Captain Ddoski rename, so the
// deployed hostname still reads "agentshield" — renaming it requires an
// actual redeploy in the Render dashboard, not just an env/config edit.
// The local alias Claude/Cursor/VS Code show the user is ours to set, though.
const MCP_URL = "https://agentshield-mcp.onrender.com/mcp";
const MCP_NAME = "captain-ddoski";
const CLAUDE_COMMAND = `claude mcp add ${MCP_NAME} -- npx -y mcp-remote ${MCP_URL}`;

// Precomputed (not derived at runtime) so this stays deterministic across
// server and client renders: base64 of {"url":MCP_URL} for Cursor,
// URL-encoded {"type":"http","url":MCP_URL} for VS Code.
const CURSOR_DEEPLINK =
  `cursor://anysphere.cursor-deeplink/mcp/install?name=${MCP_NAME}` +
  "&config=eyJ1cmwiOiJodHRwczovL2FnZW50c2hpZWxkLW1jcC5vbnJlbmRlci5jb20vbWNwIn0=";

const VSCODE_DEEPLINK =
  `vscode:mcp/install?name=${MCP_NAME}` +
  "&config=%7B%22type%22%3A%22http%22%2C%22url%22%3A%22https%3A%2F%2Fagentshield-mcp.onrender.com%2Fmcp%22%7D";

export function McpInstall() {
  const [copied, setCopied] = useState(false);

  async function copyCommand() {
    await navigator.clipboard.writeText(CLAUDE_COMMAND);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <ComicPanel className="p-6">
      <div className="mb-4 flex items-center gap-3">
        <MascotAvatar pose="pointForward" size="md" />
        <div>
          <h2 className="font-comic text-2xl text-(--comic-ink)">One-Click Install!</h2>
          <p className="text-sm font-semibold text-(--comic-ink)/70">
            Give your own agent the shield &mdash; add the Captain Ddoski MCP server.
          </p>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-3">
        <a href={CURSOR_DEEPLINK} className="comic-pop bg-(--comic-blue) px-5 py-2.5 text-sm text-white">
          Add to Cursor
        </a>
        <a href={VSCODE_DEEPLINK} className="comic-pop bg-(--comic-purple) px-5 py-2.5 text-sm text-white">
          Add to VS Code
        </a>
      </div>

      <div className="rounded-lg border-[3px] border-(--comic-ink) bg-white p-4">
        <div className="mb-2 flex items-center gap-2 font-comic text-base text-(--comic-ink)">
          <Terminal className="size-4" />
          Claude Code
        </div>
        <div className="flex items-stretch gap-2">
          <code className="min-w-0 flex-1 overflow-x-auto rounded border-2 border-(--comic-ink)/30 bg-muted px-3 py-2 font-mono text-xs whitespace-nowrap text-foreground">
            {CLAUDE_COMMAND}
          </code>
          <button
            onClick={copyCommand}
            className={cn(
              "comic-pop shrink-0 px-3 text-xs",
              copied ? "bg-(--comic-green) text-(--comic-ink)" : "bg-(--comic-yellow) text-(--comic-ink)",
            )}
          >
            {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          </button>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Run the command, then <code className="font-mono">/mcp</code> inside Claude Code to authenticate.
        </p>
      </div>
    </ComicPanel>
  );
}
