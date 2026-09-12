import type { Metadata } from "next";
import { Inter } from "next/font/google";

import "./globals.css";

// One variable family across the product; `display: swap` keeps first paint instant on a cold load.
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: { default: "CareFlow AI", template: "%s · CareFlow AI" },
  description: "Hospital information platform with authorization-aware ML, RAG and AI assistance (synthetic demo data).",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
