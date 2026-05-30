import { Link } from "react-router-dom";

import { useAuth } from "../auth";

export function Home() {
  const { user } = useAuth();
  return (
    <section aria-labelledby="home-heading">
      <h2 id="home-heading">Welcome</h2>
      <p>
        This is the SentinelQA React + Vite example. It talks to the FastAPI
        backend (<code>examples/fastapi/</code>) over HTTP. Boot both with{" "}
        <code>make demo-fastapi</code> and <code>make demo-react-vite</code>.
      </p>
      {user ? (
        <p>
          Signed in as <strong>{user}</strong>. Visit{" "}
          <Link to="/projects">Projects</Link>.
        </p>
      ) : (
        <p>
          <Link to="/login">Log in</Link> to manage projects.
        </p>
      )}
    </section>
  );
}
