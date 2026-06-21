import type { Metadata } from "next";
import { Bangers, Hanken_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AppNav } from "@/components/app-nav";

// Hanken Grotesk: the display/body face for the Captain Ddoski design system
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

// Bangers: comic-book lettering for the Captain Ddoski comic theme (headlines, callouts)
const bangers = Bangers({
  variable: "--font-comic",
  subsets: ["latin"],
  weight: ["400"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Captain Ddoski — Source Credibility for AI Agents",
  description:
    "Credibility infrastructure for AI agents. Validate a finance source before you trust it.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // No "dark" class — full light mode
    <html lang="en" className={`${hankenGrotesk.variable} ${jetbrainsMono.variable} ${bangers.variable} h-full`}>
      <body className="min-h-full flex flex-col bg-background text-foreground antialiased">
        <AppNav />
        <main className="flex-1 pb-20 md:pb-0">{children}</main>
      </body>
    </html>
  );
}
