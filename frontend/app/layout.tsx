import type { Metadata, Viewport } from "next";
import { Barlow_Semi_Condensed, Inter } from "next/font/google";

import "./globals.css";

// Inter carries prose and tables; Barlow Semi Condensed carries channel labels and monitor numerics.
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const barlow = Barlow_Semi_Condensed({
  subsets: ["latin"], weight: ["500", "600", "700"], variable: "--font-barlow", display: "swap",
});

export const metadata: Metadata = {
  title: { default: "CareFlow AI", template: "%s · CareFlow AI" },
  description: "Hospital information platform with authorization-aware ML, RAG and AI assistance (synthetic demo data).",
};

export const viewport: Viewport = { themeColor: "#070707", colorScheme: "dark" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} ${barlow.variable}`}>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
