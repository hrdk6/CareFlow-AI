import type { Metadata, Viewport } from "next";
import { Hanken_Grotesk, Inter } from "next/font/google";

import "./globals.css";

// Inter carries text and tables; Hanken Grotesk carries headings, figures and the wordmark.
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const hanken = Hanken_Grotesk({
  subsets: ["latin"], weight: ["500", "600", "700"], variable: "--font-hanken", display: "swap",
});

export const metadata: Metadata = {
  title: { default: "CareFlow AI", template: "%s · CareFlow AI" },
  description: "Hospital information platform with authorization-aware ML, RAG and AI assistance (synthetic demo data).",
};

export const viewport: Viewport = { themeColor: "#f3f6f7", colorScheme: "light" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} ${hanken.variable}`}>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
