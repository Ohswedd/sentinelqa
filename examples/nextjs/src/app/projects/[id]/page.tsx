import { notFound, redirect } from "next/navigation";

import { getSession } from "@/lib/auth";
import { getProject } from "@/lib/db";

export default async function ProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const session = await getSession();
  if (!session) redirect("/login");
  const { id } = await params;
  const numericId = Number(id);
  if (!Number.isFinite(numericId)) notFound();
  const project = getProject(numericId, session.username);
  if (!project) notFound();
  return (
    <section aria-labelledby="project-heading">
      <h2 id="project-heading">{project.name}</h2>
      <p>{project.description || "No description."}</p>
      <p>
        <a href="/projects">Back to projects</a>
      </p>
    </section>
  );
}
