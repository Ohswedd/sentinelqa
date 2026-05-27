// Single source of truth for the runtime version. Bump in lockstep with
// package.json. The build step does NOT regenerate this — the file is the
// authoritative version so we never depend on package.json being on disk
// at runtime (the bin runs from `dist/`, two directories away).
export const PACKAGE_NAME = '@sentinelqa/ts-runtime';
export const VERSION = '0.0.0';
