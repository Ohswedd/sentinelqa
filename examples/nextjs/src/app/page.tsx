import Link from "next/link";

import { getSession } from "@/lib/auth";

export default async function HomePage() {
  const session = await getSession();
  return (
    <section aria-labelledby="home-heading">
      <h2 id="home-heading">Welcome</h2>
      <p>
        This is the SentinelQA Next.js demo. Log in to manage projects, or visit the
        <Link href="/dashboard"> dashboard</Link>.
      </p>
      {session ? (
        <p>
          Signed in as <strong>{session.username}</strong>.
        </p>
      ) : (
        <p>
          Use the credentials in <code>README.md</code> to <Link href="/login">log in</Link>.
        </p>
      )}
    </section>
  );
}
