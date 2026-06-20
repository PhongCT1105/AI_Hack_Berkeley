import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AppNav } from "@/components/app-nav";

// Inter: the clean sans-serif used by Vercel, Linear, Datadog, Notion
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

// JetBrains Mono for trace IDs, token counts, code snippets
const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "AgentShield — Source Credibility for AI Agents",
  description:
    "Credibility infrastructure for AI agents. Validate a finance source before you trust it.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // No "dark" class — full light mode
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable} h-full`}>
      <body className="min-h-full flex flex-col bg-background text-foreground antialiased">
        <AppNav />
        <main className="flex-1">{children}</main>
      </body>
    </html>
  );
}
