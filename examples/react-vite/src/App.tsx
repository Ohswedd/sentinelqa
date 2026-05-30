import { Link, Outlet } from "react-router-dom";

import { AuthProvider, useAuth } from "./auth";

function Header() {
  const { user, signOut } = useAuth();
  return (
    <header style={{ marginBottom: "1.5rem" }}>
      <h1>SentinelQA React + Vite Demo</h1>
      <nav aria-label="Primary">
        <Link to="/">Home</Link>
        <span style={{ marginLeft: "0.75rem" }}>
          <Link to="/projects">Projects</Link>
        </span>
        <span style={{ marginLeft: "0.75rem" }}>
          {user ? (
            <button type="button" onClick={signOut}>
              Sign out ({user})
            </button>
          ) : (
            <Link to="/login">Log in</Link>
          )}
        </span>
      </nav>
    </header>
  );
}

export function App() {
  return (
    <AuthProvider>
      <div
        style={{
          fontFamily: "system-ui, sans-serif",
          maxWidth: "48rem",
          margin: "2rem auto",
          padding: "0 1rem",
          lineHeight: 1.4,
        }}
      >
        <Header />
        <main>
          <Outlet />
        </main>
      </div>
    </AuthProvider>
  );
}
