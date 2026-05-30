import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { getSession } from "@/lib/auth";

import "./globals.css";

export const metadata: Metadata = {
  title: "SentinelQA Next.js Demo",
  description: "A small Next.js 14 app the SentinelQA Phase 26 examples audit.",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const session = await getSession();
  return (
    <html lang="en">
      <body>
        <header>
          <h1>SentinelQA Next.js Demo</h1>
          <nav aria-label="Primary">
            <Link href="/">Home</Link>
            <Link href="/projects">Projects</Link>
            <Link href="/dashboard">Dashboard</Link>
            {session?.role === "admin" ? <Link href="/admin">Admin</Link> : null}
            {session ? (
              <form action="/api/auth/logout" method="post" className="inline">
                <button type="submit">Sign out ({session.username})</button>
              </form>
            ) : (
              <Link href="/login">Log in</Link>
            )}
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
