// TypeScript mirror of `engine.policy.redaction`.
// Python owns the rules. They are exported by
// `scripts/export-redaction-rules.py` into
// `packages/shared-schema/redaction-rules.json` and consumed here. CI
// re-runs the exporter in `--check` mode so the JSON cannot drift from
// the Python source.
// Parity guarantee: for every input in
// `tests/golden/redaction/parity.json`, the Python `redact()` and the
// TS `redact()` produce byte-identical output.

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export interface ValueRuleSpec {
  readonly category: string;
  readonly pattern: string;
  readonly flags: readonly string[];
  readonly description: string;
}

export interface RedactionRules {
  readonly schema_version: string;
  readonly description: string;
  readonly secret_key_names: readonly string[];
  readonly category_for_key: Readonly<Record<string, string>>;
  readonly url_secret_query_keys: readonly string[];
  readonly always_redact_headers: readonly string[];
  readonly value_rules: readonly ValueRuleSpec[];
  readonly entropy: {
    readonly min_token_length: number;
    readonly min_bits_per_char: number;
    readonly pattern: string;
  };
  readonly redacted_template: string;
}

interface CompiledRule {
  readonly category: string;
  readonly regex: RegExp;
  readonly replacement: string;
}

interface CompiledRules {
  readonly raw: RedactionRules;
  readonly secretKeyNames: ReadonlySet<string>;
  readonly categoryForKey: ReadonlyMap<string, string>;
  readonly urlSecretQueryKeys: ReadonlySet<string>;
  readonly alwaysRedactHeaders: ReadonlySet<string>;
  readonly valueRules: readonly CompiledRule[];
  readonly entropyRegex: RegExp;
  readonly entropyMinLength: number;
  readonly entropyMinBits: number;
  readonly template: (category: string) => string;
}

// ---------------------------------------------------------------------
// Rule loading + compilation
// ---------------------------------------------------------------------

let _cached: CompiledRules | null = null;

function defaultRulesPath(): string {
  const here = dirname(fileURLToPath(import.meta.url));
  // src/redact.ts → ../shared-schema/redaction-rules.json (workspace layout)
  return resolve(here, '..', '..', 'shared-schema', 'redaction-rules.json');
}

export function loadRedactionRules(path: string = defaultRulesPath()): RedactionRules {
  const raw = readFileSync(path, 'utf8');
  return JSON.parse(raw) as RedactionRules;
}

function compileFlags(flags: readonly string[]): string {
  // Python flag → JS flag mapping. Anything we don't know about, we drop
  // (the rule still compiles, just less permissive).
  const map: Record<string, string> = {
    IGNORECASE: 'i',
    MULTILINE: 'm',
    DOTALL: 's',
  };
  // Patterns are global by default so .replace() replaces every occurrence.
  let out = 'g';
  for (const f of flags) {
    const ch = map[f];
    if (ch && !out.includes(ch)) out += ch;
  }
  return out;
}

function pythonPatternToJs(pattern: string): string {
  // The Python rules use the (?i) inline flag prefix in two places. JS
  // does not support inline-flag syntax, but compileFlags() already
  // promotes IGNORECASE via the `i` flag, so we just strip the prefix.
  // Anything else we leave alone — the patterns are intentionally simple
  // (no lookbehind, no \A/\Z, no named groups beyond what JS supports).
  return pattern.replace(/^\(\?[a-z]+\)/, '');
}

function compile(raw: RedactionRules): CompiledRules {
  const compiledRules: CompiledRule[] = raw.value_rules.map((rule) => {
    const flags = compileFlags(
      rule.pattern.startsWith('(?i)')
        ? Array.from(new Set([...rule.flags, 'IGNORECASE']))
        : rule.flags,
    );
    const regex = new RegExp(pythonPatternToJs(rule.pattern), flags);
    return {
      category: rule.category,
      regex,
      replacement: raw.redacted_template.replace('{category}', rule.category),
    };
  });

  return {
    raw,
    secretKeyNames: new Set(raw.secret_key_names),
    categoryForKey: new Map(Object.entries(raw.category_for_key)),
    urlSecretQueryKeys: new Set(raw.url_secret_query_keys),
    alwaysRedactHeaders: new Set(raw.always_redact_headers),
    valueRules: compiledRules,
    entropyRegex: new RegExp(raw.entropy.pattern, 'g'),
    entropyMinLength: raw.entropy.min_token_length,
    entropyMinBits: raw.entropy.min_bits_per_char,
    template: (category: string) => raw.redacted_template.replace('{category}', category),
  };
}

function rules(): CompiledRules {
  if (_cached === null) {
    _cached = compile(loadRedactionRules());
  }
  return _cached;
}

/**
 * Reset the rule cache. Test-only — production callers always read the
 * default file.
 */
export function _resetCacheForTests(): void {
  _cached = null;
}

/**
 * Override the rule source (path or compiled doc). Test-only.
 */
export function _setRulesForTests(doc: RedactionRules): void {
  _cached = compile(doc);
}

// ---------------------------------------------------------------------
// Entropy heuristic
// ---------------------------------------------------------------------

function shannonEntropy(text: string): number {
  if (text.length === 0) return 0;
  const counts = new Map<string, number>();
  for (const ch of text) counts.set(ch, (counts.get(ch) ?? 0) + 1);
  const n = text.length;
  let h = 0;
  for (const c of counts.values()) {
    const p = c / n;
    h -= p * Math.log2(p);
  }
  return h;
}

function redactHighEntropy(value: string, r: CompiledRules): string {
  // Recreate the regex per call because /g is stateful across calls when
  // .exec() is used; .replace() with /g is safe.
  return value.replace(r.entropyRegex, (token) => {
    if (token.length < r.entropyMinLength) return token;
    if (shannonEntropy(token) >= r.entropyMinBits) {
      return r.template('high_entropy_token');
    }
    return token;
  });
}

// ---------------------------------------------------------------------
// Public surface
// ---------------------------------------------------------------------

export function redactString(value: string, r: CompiledRules = rules()): string {
  let out = value;
  for (const rule of r.valueRules) {
    out = out.replace(rule.regex, rule.replacement);
  }
  out = redactHighEntropy(out, r);
  return out;
}

const PLAIN_OBJECT_PROTOTYPE = Object.getPrototypeOf({}) as object | null;

function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (typeof value !== 'object' || value === null) return false;
  const proto: unknown = Object.getPrototypeOf(value);
  return proto === PLAIN_OBJECT_PROTOTYPE || proto === null;
}

function keyCategory(key: string, r: CompiledRules): string | null {
  const normalized = key.toLowerCase().replace(/-/g, '_');
  if (r.secretKeyNames.has(normalized) || r.secretKeyNames.has(key.toLowerCase())) {
    return r.categoryForKey.get(normalized) ?? 'secret_field';
  }
  return null;
}

const DEFAULT_DEPTH = 6;

export function redact(value: unknown, depth: number = DEFAULT_DEPTH): unknown {
  return _redact(value, depth, rules());
}

function _redact(value: unknown, depth: number, r: CompiledRules): unknown {
  if (depth <= 0) {
    return r.template('depth_limit');
  }
  if (value === null || value === undefined) return value;
  if (typeof value === 'boolean' || typeof value === 'number') return value;
  if (typeof value === 'string') return redactString(value, r);
  if (Array.isArray(value)) {
    return value.map((item) => _redact(item, depth - 1, r));
  }
  if (value instanceof Set) {
    return Array.from(value).map((item) => _redact(item, depth - 1, r));
  }
  if (isPlainObject(value)) {
    const out: Record<string, unknown> = {};
    for (const [key, sub] of Object.entries(value)) {
      const category = keyCategory(key, r);
      if (category !== null && sub !== null && sub !== undefined && sub !== '') {
        out[key] = r.template(category);
      } else {
        out[key] = _redact(sub, depth - 1, r);
      }
    }
    return out;
  }
  // Unknown object types fall back to their string form (mirrors Python's
  // `repr(value)` fallback). We never let an opaque object out unfiltered.
  // Date, Map, custom classes etc. land here.
  return redactString(stringifyOpaque(value), r);
}

function stringifyOpaque(value: unknown): string {
  if (value instanceof Date) return value.toISOString();
  if (value instanceof Error) return `${value.name}: ${value.message}`;
  try {
    return JSON.stringify(value) ?? String(value);
  } catch {
    return String(value);
  }
}

/**
 * Case-insensitive HTTP header redaction. The always-redact list is a
 * strict superset of `secret_key_names` to ensure HTTP framing always
 * wins.
 */
export function redactHeaders(headers: Record<string, string>): Record<string, string> {
  const r = rules();
  const out: Record<string, string> = {};
  for (const [name, value] of Object.entries(headers)) {
    const lowered = name.toLowerCase();
    if (r.alwaysRedactHeaders.has(lowered)) {
      out[name] = r.template(lowered);
    } else {
      out[name] = redactString(value, r);
    }
  }
  return out;
}

/**
 * Strip userinfo from the netloc and redact secret-shaped query params.
 * Returns the URL as a string; non-URL inputs are returned unchanged
 * (Python raises; we are permissive here because Playwright sometimes
 * hands us route patterns).
 *
 * URL byte-form is NOT guaranteed to match Python exactly (Python uses
 * `urllib.parse.quote(safe='[]:')` to keep the marker readable; JS's
 * URLSearchParams percent-encodes more aggressively). The contract is
 * behavioural: the secret value never appears in the output, and the
 * marker `[REDACTED:url_token]` is present in some form for each
 * secret-shaped query key. The parity test exercises this with
 * `assertUrlRedaction`, not byte equality.
 */
export function redactUrl(rawUrl: string): string {
  const r = rules();
  let parsed: URL;
  try {
    parsed = new URL(rawUrl);
  } catch {
    return rawUrl;
  }

  const hasUserinfo = parsed.username !== '' || parsed.password !== '';

  const queryPieces: string[] = [];
  for (const [key, value] of parsed.searchParams.entries()) {
    const outValue = r.urlSecretQueryKeys.has(key.toLowerCase())
      ? r.template('url_token')
      : redactString(value, r);
    queryPieces.push(`${pythonQuote(key)}=${pythonQuote(outValue)}`);
  }
  const query = queryPieces.length > 0 ? `?${queryPieces.join('&')}` : '';

  const auth = hasUserinfo ? '[REDACTED:userinfo]@' : '';
  // parsed.host already excludes userinfo and is in lowercase canonical form.
  const port = parsed.port ? `:${parsed.port}` : '';
  const hostBase = parsed.hostname;
  return `${parsed.protocol}//${auth}${hostBase}${port}${parsed.pathname}${query}${parsed.hash}`;
}

/**
 * Mirror Python's `urllib.parse.quote(s, safe='[]:')` — encodes
 * everything except [a-zA-Z0-9_.\-~] and the characters in `safe`.
 */
function pythonQuote(s: string, safe = '[]:'): string {
  const safeSet = new Set([...safe]);
  let out = '';
  for (const ch of s) {
    const code = ch.codePointAt(0);
    if (code === undefined) continue;
    if (
      (code >= 0x30 && code <= 0x39) ||
      (code >= 0x41 && code <= 0x5a) ||
      (code >= 0x61 && code <= 0x7a) ||
      ch === '_' ||
      ch === '.' ||
      ch === '-' ||
      ch === '~' ||
      safeSet.has(ch)
    ) {
      out += ch;
      continue;
    }
    // Encode each UTF-8 byte of the codepoint.
    const utf8 = new TextEncoder().encode(ch);
    for (const b of utf8) {
      out += '%' + b.toString(16).toUpperCase().padStart(2, '0');
    }
  }
  return out;
}
