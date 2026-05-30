import { redirect } from "next/navigation";

import { getSession } from "@/lib/auth";

export default async function AdminPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  if (session.role !== "admin") {
    return (
      <section aria-labelledby="admin-heading">
        <h2 id="admin-heading">Admin</h2>
        <p role="alert" className="alert">
          You do not have permission to view this page.
        </p>
      </section>
    );
  }
  return (
    <section aria-labelledby="admin-heading">
      <h2 id="admin-heading">Admin</h2>
      <p>
        Welcome, {session.username}. This page would normally surface user / project
        administration. For the demo it is a placeholder gated on the <code>admin</code> role.
      </p>
    </section>
  );
}
