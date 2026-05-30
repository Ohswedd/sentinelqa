import { cookies } from "next/headers";

const SESSION_COOKIE = "sentinel_demo_session";

const DEMO_USERS: Record<string, { password: string; role: "user" | "admin" }> = {
  demo: { password: "demo", role: "user" },
  admin: { password: "admin", role: "admin" },
};

export interface Session {
  username: string;
  role: "user" | "admin";
}

export function authenticate(username: string, password: string): Session | null {
  const entry = DEMO_USERS[username];
  if (!entry || entry.password !== password) return null;
  return { username, role: entry.role };
}

export async function setSession(session: Session): Promise<void> {
  const store = await cookies();
  store.set(SESSION_COOKIE, JSON.stringify(session), {
    httpOnly: true,
    sameSite: "lax",
    secure: false,
    path: "/",
  });
}

export async function clearSession(): Promise<void> {
  const store = await cookies();
  store.delete(SESSION_COOKIE);
}

export async function getSession(): Promise<Session | null> {
  const store = await cookies();
  const raw = store.get(SESSION_COOKIE)?.value;
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Session;
    if (typeof parsed.username !== "string") return null;
    if (parsed.role !== "user" && parsed.role !== "admin") return null;
    return parsed;
  } catch {
    return null;
  }
}
