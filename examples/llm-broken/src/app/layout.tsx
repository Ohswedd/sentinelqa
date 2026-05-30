import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "SentinelQA LLM-Broken Demo (DO NOT DEPLOY)",
  description:
    "Deliberately broken Next.js app for SentinelQA Phase 19 / 26 LLM-audit demos.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body
        style={{
          fontFamily: "system-ui, sans-serif",
          margin: "2rem auto",
          maxWidth: "48rem",
          padding: "0 1rem",
          lineHeight: 1.4,
        }}
      >
        <header>
          <h1>LLM-Broken Demo</h1>
          <p role="note" style={{ color: "#b91c1c" }}>
            This app is intentionally broken. Do not deploy.
          </p>
          <nav aria-label="Primary">
            <Link href="/" style={{ marginRight: "0.75rem" }}>
              Home
            </Link>
            <Link href="/dashboard" style={{ marginRight: "0.75rem" }}>
              Dashboard
            </Link>
            <Link href="/checkout" style={{ marginRight: "0.75rem" }}>
              Checkout
            </Link>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
