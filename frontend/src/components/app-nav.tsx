"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import { useResults } from "@/lib/api";
import { cn } from "@/lib/utils";

const links = [
  { href: "/", label: "Dashboard", exact: true },
  { href: "/arena", label: "Terac Arena", exact: false },
];

export function AppNav() {
  const pathname = usePathname();
  const hasThreats = useResults().some((result) => result.recommendation === "AVOID");
  const navLinks = [
    ...links,
    { href: "/threats", label: "Threat Feed", exact: false, indicator: hasThreats },
  ];

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-white/95 backdrop-blur supports-backdrop-filter:bg-white/80">
      {/* Purple accent bar at the very top — Datadog-style */}
      <div className="h-0.5 w-full bg-linear-to-r from-violet-600 via-purple-500 to-indigo-500" />

      <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-6">
        {/* Brand */}
        <Link href="/" className="flex items-center gap-2.5 font-semibold text-gray-900">
          <span className="flex size-7 items-center justify-center rounded-lg bg-violet-600 text-white shadow-sm">
            <ShieldCheck className="size-4" />
          </span>
          <span className="text-base tracking-tight">AgentShield</span>
          <span className="rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-violet-600">
            Finance
          </span>
        </Link>

        {/* Nav links */}
        <nav className="flex items-center gap-1">
          {navLinks.map((l) => {
            const active = l.exact ? pathname === l.href : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-150",
                  active
                    ? "bg-violet-50 text-violet-700"
                    : "text-gray-500 hover:bg-gray-100 hover:text-gray-900",
                )}
              >
                <span className="inline-flex items-center gap-1.5">
                  {l.label}
                  {"indicator" in l && l.indicator && (
                    <span className="size-1.5 rounded-full bg-red-500" />
                  )}
                </span>
              </Link>
            );
          })}
        </nav>

        {/* Right side */}
        <div className="ml-auto flex items-center gap-3 text-xs text-gray-400">
          <span className="hidden sm:block">Credibility infra for AI agents</span>
          <span className="flex items-center gap-1.5 rounded-full border border-green-200 bg-green-50 px-2.5 py-1 text-green-700">
            <span className="size-1.5 animate-pulse rounded-full bg-green-500" />
            Live
          </span>
        </div>
      </div>
    </header>
  );
}
