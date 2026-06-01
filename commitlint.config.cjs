/**
 * SentinelQA commitlint configuration.
 *
 * Enforces Conventional Commits per the engineering guidelines with a deliberately narrow
 * type whitelist. The whitelist matches the one documented in
 * docs/dev/commits.md; any change to either file must be mirrored in the
 * other.
 *
 * Wired in via .pre-commit-config.yaml (commit-msg stage). Bypassing the hook
 * with --no-verify is forbidden by the engineering guidelines unless explicitly authorized.
 */

module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    // the engineering guidelines type whitelist
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'docs', 'test', 'refactor', 'security', 'ci', 'chore', 'perf', 'build'],
    ],
    'type-case': [2, 'always', 'lower-case'],
    'type-empty': [2, 'never'],
    'scope-empty': [1, 'never'], // scopes are encouraged but not strictly required
    'scope-case': [2, 'always', 'kebab-case'],
    'subject-empty': [2, 'never'],
    // Subjects often legitimately contain proper nouns ("SentinelQA", "the documentation", "CI"),
    // so do not force a single case style on the subject line.
    'subject-case': [0],
    // Cap headline length so commit lists stay scannable, but leave room for
    // module names like "(typescript-tooling)".
    'header-max-length': [2, 'always', 100],
    'body-max-line-length': [2, 'always', 200],
    'footer-max-line-length': [2, 'always', 200],
  },
};
