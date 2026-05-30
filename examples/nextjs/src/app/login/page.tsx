import { redirect } from "next/navigation";

import { authenticate, getSession, setSession } from "@/lib/auth";

async function loginAction(formData: FormData): Promise<void> {
  "use server";
  const username = String(formData.get("username") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const session = authenticate(username, password);
  if (!session) {
    redirect("/login?error=1");
  }
  await setSession(session);
  redirect("/projects");
}

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const session = await getSession();
  if (session) redirect("/projects");
  const params = await searchParams;
  return (
    <section aria-labelledby="login-heading">
      <h2 id="login-heading">Log in</h2>
      {params.error ? (
        <p role="alert" className="alert">
          Invalid username or password.
        </p>
      ) : null}
      <form action={loginAction}>
        <p>
          <label htmlFor="username">Username</label>
          <br />
          <input id="username" name="username" autoComplete="username" required />
        </p>
        <p>
          <label htmlFor="password">Password</label>
          <br />
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
          />
        </p>
        <p>
          <button type="submit">Sign in</button>
        </p>
      </form>
    </section>
  );
}
