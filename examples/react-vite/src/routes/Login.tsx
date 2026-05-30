import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth";

export function Login() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("demo");
  const [token, setToken] = useState("demo-token");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!username.trim() || !token.trim()) {
      setError("Username and token are required.");
      return;
    }
    setError(null);
    signIn(username.trim(), token.trim());
    navigate("/projects");
  }

  return (
    <section aria-labelledby="login-heading">
      <h2 id="login-heading">Log in</h2>
      <p>
        The FastAPI backend uses a single demo bearer token. Defaults are
        prefilled below.
      </p>
      <form onSubmit={handleSubmit}>
        <p>
          <label htmlFor="username">Username</label>
          <br />
          <input
            id="username"
            name="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </p>
        <p>
          <label htmlFor="token">API token</label>
          <br />
          <input
            id="token"
            name="token"
            type="password"
            autoComplete="current-password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            required
          />
        </p>
        {error && (
          <p role="alert" style={{ color: "#b91c1c" }}>
            {error}
          </p>
        )}
        <p>
          <button type="submit">Sign in</button>
        </p>
      </form>
    </section>
  );
}
