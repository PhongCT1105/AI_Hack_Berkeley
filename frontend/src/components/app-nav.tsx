"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Gauge, Menu, Radar, Scale, Shield, Sparkles } from "lucide-react";
import { useResults } from "@/lib/api";
import { cn } from "@/lib/utils";

const links = [
  { href: "/demo", label: "Run", exact: false, icon: Sparkles },
  { href: "/arena", label: "Compare", exact: false, icon: Scale },
  { href: "/", label: "Monitor", exact: true, icon: Gauge },
];

export function AppNav() {
  const pathname = usePathname();
  const hasThreats = useResults().some((result) => result.recommendation === "AVOID");
  const navLinks = [...links, { href: "/threats", label: "Threats", exact: false, icon: Radar, indicator: hasThreats }];
  const mobileLinks = links;

  return (
    <>
      {/* TopAppBar */}
      <header className="sticky top-0 z-50 border-b border-border/70 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4 sm:px-6">
          {/* Brand */}
          <Link href="/" className="flex items-center gap-2.5 active:scale-95 duration-150">
            <Shield className="size-5 text-primary" />
            <span className="text-lg font-bold tracking-tighter text-foreground">Shield Terminal</span>
          </Link>

          {/* Nav links */}
          <nav className="hidden items-center gap-1 md:flex">
            {navLinks.map((l) => {
              const active = l.exact ? pathname === l.href : pathname.startsWith(l.href);
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  className={cn(
                    "rounded px-3 py-1.5 text-xs font-semibold tracking-wide uppercase transition-colors duration-150",
                    active
                      ? "bg-secondary text-primary"
                      : "text-muted-foreground hover:text-primary",
                  )}
                >
                  <span className="inline-flex items-center gap-1.5">
                    {l.label}
                    {"indicator" in l && l.indicator && (
                      <span className="size-1.5 rounded-full bg-destructive pulse-dot" />
                    )}
                  </span>
                </Link>
              );
            })}
          </nav>

          {/* Right side */}
          <div className="ml-auto flex items-center gap-3 text-xs text-muted-foreground">
            <span className="hidden lg:block">Source trust infrastructure</span>
            <span className="flex items-center gap-1.5 rounded border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-emerald-700">
              <span className="size-1.5 rounded-full bg-emerald-500 pulse-dot" />
              Live
            </span>
            <Menu className="size-4 md:hidden" />
          </div>
        </div>
      </header>

      {/* BottomNavBar (mobile only) */}
      <nav className="fixed bottom-0 left-0 z-50 flex h-16 w-full items-center justify-around border-t border-border/70 bg-background/90 px-4 backdrop-blur-md shadow-lg md:hidden">
        {mobileLinks.map((l) => {
          const active = l.exact ? pathname === l.href : pathname.startsWith(l.href);
          const Icon = l.icon;
          return (
            <Link
              key={l.href}
              href={l.href}
              className={cn(
                "flex min-w-16 flex-col items-center justify-center gap-0.5 rounded px-3 py-1 transition-all active:scale-90",
                active ? "bg-primary text-primary-foreground" : "text-muted-foreground",
              )}
            >
              <Icon className="size-5" />
              <span className="text-[10px] font-semibold uppercase tracking-wide">{l.label}</span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
