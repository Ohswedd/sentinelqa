import { redirect } from "next/navigation";

import { getSession } from "@/lib/auth";
import { listProjects } from "@/lib/db";

export default async function DashboardPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  const projects = listProjects(session.username);
  return (
    <section aria-labelledby="dashboard-heading">
      <h2 id="dashboard-heading">Dashboard</h2>
      <p>Signed in as {session.username}.</p>
      <ul>
        <li>Project count: {projects.length}</li>
        <li>Role: {session.role}</li>
      </ul>
    </section>
  );
}
