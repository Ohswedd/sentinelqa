"use client";

import { useEffect, useState } from "react";

export default function AdminPage() {
  const [users, setUsers] = useState<string[]>([]);

  // LLM-broken anti-pattern: /admin is hidden from the nav but the page itself
  // performs no role check — frontend-only auth. Hitting /admin directly works.
  useEffect(() => {
    setUsers(["alice", "bob", "carol"]);
  }, []);

  return (
    <section aria-labelledby="admin-heading">
      <h2 id="admin-heading">Admin (unauthorized — but who's checking?)</h2>
      <ul>
        {users.map((u) => (
          <li key={u}>{u}</li>
        ))}
      </ul>
    </section>
  );
}
