// Public API for `@sentinelqa/ts-runtime`. PRD §15, CLAUDE.md §8/§21.
//
// Re-exports here are part of the package contract. Internal helpers
// must stay in their own modules and be reached through the subpath
// exports declared in `package.json` (`./protocol`, `./playwright`,
// `./locators`). Until Phase 04 finishes wiring every helper, this
// barrel keeps only the cross-cutting primitives.
export { PACKAGE_NAME, VERSION } from './version.js';
