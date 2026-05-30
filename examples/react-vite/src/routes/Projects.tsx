import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Api, Project } from "../api";
import { useAuth } from "../auth";

export function Projects() {
  const { token } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const items = await Api.listProjects(token);
      setProjects(items);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !name.trim()) return;
    try {
      await Api.createProject(token, name.trim(), description.trim());
      setName("");
      setDescription("");
      await reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleDelete(id: number) {
    if (!token) return;
    try {
      await Api.deleteProject(token, id);
      await reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (!token) {
    return (
      <section aria-labelledby="projects-heading">
        <h2 id="projects-heading">Projects</h2>
        <p>
          You need to <Link to="/login">log in</Link> first.
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby="projects-heading">
      <h2 id="projects-heading">Projects</h2>
      {error && (
        <p role="alert" style={{ color: "#b91c1c" }}>
          {error}
        </p>
      )}
      {loading ? (
        <p aria-live="polite">Loading projects…</p>
      ) : (
        <table>
          <caption className="sr-only">List of projects</caption>
          <thead>
            <tr>
              <th scope="col">ID</th>
              <th scope="col">Name</th>
              <th scope="col">Description</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((p) => (
              <tr key={p.id}>
                <td>{p.id}</td>
                <td>{p.name}</td>
                <td>{p.description}</td>
                <td>
                  <button
                    type="button"
                    aria-label={`Delete ${p.name}`}
                    onClick={() => handleDelete(p.id)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <h3>Create project</h3>
      <form onSubmit={handleCreate}>
        <p>
          <label htmlFor="new-name">Name</label>
          <br />
          <input
            id="new-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </p>
        <p>
          <label htmlFor="new-description">Description</label>
          <br />
          <input
            id="new-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </p>
        <p>
          <button type="submit">Create</button>
        </p>
      </form>
    </section>
  );
}
