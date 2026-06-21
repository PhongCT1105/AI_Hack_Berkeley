"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Menu, Radar, Scale, Shield, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

const links = [
  { href: "/demo", label: "Run Shield", shortLabel: "Run", exact: false, icon: ShieldCheck },
  { href: "/compare", label: "Compare pipelines", shortLabel: "Compare", exact: false, icon: Scale },
  { href: "/eval", label: "View model evaluation", shortLabel: "Evaluate", exact: false, icon: Activity },
  { href: "/threats", label: "Review threat feed", shortLabel: "Threats", exact: false, icon: Radar },
];

export function AppNav() {
  const pathname = usePathname();
  const navLinks = links;

  return (
    <>
      {/* TopAppBar */}
      <header className="sticky top-0 z-50 border-b border-border/70 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-4 sm:px-6">
          {/* Brand */}
          <Link href="/" className="flex items-center gap-2.5 active:scale-95 duration-150">
            <Shield className="size-5 text-primary" />
            <span className="text-lg font-bold tracking-tighter text-foreground">Captain America</span>
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
                    "rounded px-2 py-1.5 text-sm font-medium transition-colors duration-150",
                    active
                      ? "text-primary"
                      : "text-muted-foreground hover:text-primary",
                  )}
                >
                  <span className="inline-flex items-center gap-1.5">
                    <l.icon className="size-3.5" />
                    {l.label}
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
        {links.map((l) => {
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
              <span className="text-[10px] font-semibold tracking-wide">{l.shortLabel}</span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
