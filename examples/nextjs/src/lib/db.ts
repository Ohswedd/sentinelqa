export interface Project {
  id: number;
  name: string;
  description: string;
  owner: string;
}

const _projects = new Map<number, Project>([
  [1, { id: 1, name: "SentinelQA", description: "The release-confidence engine.", owner: "demo" }],
  [2, { id: 2, name: "Internal Docs", description: "Docs site for the team.", owner: "demo" }],
]);
let _nextId = 3;

export function listProjects(owner: string): Project[] {
  return Array.from(_projects.values())
    .filter((p) => p.owner === owner)
    .sort((a, b) => a.id - b.id);
}

export function getProject(id: number, owner: string): Project | null {
  const p = _projects.get(id);
  if (!p || p.owner !== owner) return null;
  return p;
}

export function createProject(name: string, description: string, owner: string): Project {
  const id = _nextId++;
  const project: Project = { id, name, description, owner };
  _projects.set(id, project);
  return project;
}

export function updateProject(
  id: number,
  patch: { name?: string; description?: string },
  owner: string,
): Project | null {
  const existing = _projects.get(id);
  if (!existing || existing.owner !== owner) return null;
  const updated: Project = {
    ...existing,
    name: patch.name ?? existing.name,
    description: patch.description ?? existing.description,
  };
  _projects.set(id, updated);
  return updated;
}

export function deleteProject(id: number, owner: string): boolean {
  const existing = _projects.get(id);
  if (!existing || existing.owner !== owner) return false;
  _projects.delete(id);
  return true;
}
