import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "CareFlow AI", template: "%s · CareFlow AI" },
  description: "Hospital information platform with authorization-aware ML, RAG and AI assistance (synthetic demo data).",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
