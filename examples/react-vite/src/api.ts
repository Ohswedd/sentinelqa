const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://127.0.0.1:8000";

export interface Project {
  id: number;
  name: string;
  description: string;
}

async function request<T>(
  path: string,
  init: RequestInit,
  token: string | null,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("content-type", "application/json");
  if (token) headers.set("authorization", `Bearer ${token}`);
  const resp = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${body}`);
  }
  if (resp.status === 204) return undefined as unknown as T;
  return (await resp.json()) as T;
}

export const Api = {
  listProjects: (token: string | null) => request<Project[]>("/projects", { method: "GET" }, token),
  createProject: (token: string | null, name: string, description: string) =>
    request<Project>(
      "/projects",
      { method: "POST", body: JSON.stringify({ name, description }) },
      token,
    ),
  deleteProject: (token: string | null, id: number) =>
    request<void>(`/projects/${id}`, { method: "DELETE" }, token),
};
