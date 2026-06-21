import type { Metadata } from "next";
import { Hanken_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AppNav } from "@/components/app-nav";

// Hanken Grotesk: the display/body face for the Captain America design system
const hankenGrotesk = Hanken_Grotesk({
  variable: "--font-hanken",
  subsets: ["latin"],
  weight: ["400", "600", "700"],
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
  title: "Captain America — Source Credibility for AI Agents",
  description:
    "Credibility infrastructure for AI agents. Validate a finance source before you trust it.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // No "dark" class — full light mode
    <html lang="en" className={`${hankenGrotesk.variable} ${jetbrainsMono.variable} h-full`}>
      <body className="min-h-full flex flex-col bg-background text-foreground antialiased">
        <AppNav />
        <main className="flex-1 pb-20 md:pb-0">{children}</main>
      </body>
    </html>
  );
}
