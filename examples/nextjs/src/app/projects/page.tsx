import Link from "next/link";
import { redirect } from "next/navigation";

import { getSession } from "@/lib/auth";
import { createProject, deleteProject, listProjects } from "@/lib/db";

async function createAction(formData: FormData): Promise<void> {
  "use server";
  const session = await getSession();
  if (!session) redirect("/login");
  const name = String(formData.get("name") ?? "").trim();
  const description = String(formData.get("description") ?? "").trim();
  if (!name) redirect("/projects?error=name");
  createProject(name, description, session.username);
  redirect("/projects");
}

async function deleteAction(formData: FormData): Promise<void> {
  "use server";
  const session = await getSession();
  if (!session) redirect("/login");
  const id = Number(formData.get("id"));
  if (Number.isFinite(id)) deleteProject(id, session.username);
  redirect("/projects");
}

export default async function ProjectsPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  const projects = listProjects(session.username);
  return (
    <section aria-labelledby="projects-heading">
      <h2 id="projects-heading">Projects</h2>
      <table>
        <caption className="sr-only">List of your projects</caption>
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
              <td>
                <Link href={`/projects/${p.id}`}>{p.name}</Link>
              </td>
              <td>{p.description}</td>
              <td>
                <form action={deleteAction} className="inline">
                  <input type="hidden" name="id" value={p.id} />
                  <button type="submit" aria-label={`Delete ${p.name}`}>
                    Delete
                  </button>
                </form>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3>Create project</h3>
      <form action={createAction}>
        <p>
          <label htmlFor="name">Name</label>
          <br />
          <input id="name" name="name" required />
        </p>
        <p>
          <label htmlFor="description">Description</label>
          <br />
          <input id="description" name="description" />
        </p>
        <p>
          <button type="submit">Create</button>
        </p>
      </form>
    </section>
  );
}
