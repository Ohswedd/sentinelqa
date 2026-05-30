"use client";

import { useState } from "react";

// LLM-broken anti-pattern: hardcoded admin credentials in client code.
const ADMIN_USERNAME = "admin";
const ADMIN_PASSWORD = "supersecret123";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    // LLM-broken anti-pattern: frontend-only auth — token signed in the browser.
    if (username === ADMIN_USERNAME && password === ADMIN_PASSWORD) {
      const fakeJwt = btoa(JSON.stringify({ sub: username, role: "admin" }));
      // LLM-broken anti-pattern: JWT stored in localStorage.
      window.localStorage.setItem("jwt", fakeJwt);
      window.location.href = "/dashboard";
    }
  }

  return (
    <section aria-labelledby="login-heading">
      <h2 id="login-heading">Log in</h2>
      <form onSubmit={handleSubmit}>
        <p>
          <label htmlFor="username">Username</label>
          <br />
          <input
            id="username"
            name="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </p>
        <p>
          <label htmlFor="password">Password</label>
          <br />
          <input
            id="password"
            name="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </p>
        <p>
          <button type="submit">Sign in</button>
        </p>
      </form>
    </section>
  );
}
