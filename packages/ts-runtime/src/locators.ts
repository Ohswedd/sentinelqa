// Semantic-first locator utilities (the documentation, §27 Example
// test; the engineering guidelines, §22 Generated tests).
// Two surfaces:
// 1. `bestLocator(page, target)` — pick a locator using a
// semantic-first strategy chain (getByRole → getByLabel →
// getByPlaceholder → getByText → getByTestId → getByAltText →
// getByTitle). Returns the *first* strategy whose locator matches
// exactly one element. Used by (Generator) to produce
// readable specs.
// 2. `auditLocatorBrittleness(spec)` — static analysis over a
// generated TS spec. Warns on brittle patterns
// (`page.locator('div:nth-of-type(3)')`, raw XPath, raw `page.$`
// queries, etc.). Used by as a sanity check before
// writing a spec to disk, and by (Healer) when proposing
// locator repairs.
// 3. `describeLocator(locator)` — captures the descriptor (role,
// accessible name, text, landmarks) so the Healer () can
// regenerate when the DOM changes.

import { Project, SyntaxKind } from 'ts-morph';

// ---------------------------------------------------------------------
// Element target + strategy types
// ---------------------------------------------------------------------

export interface ElementTarget {
  readonly role?: string;
  readonly accessibleName?: string | RegExp;
  readonly label?: string;
  readonly placeholder?: string;
  readonly text?: string;
  readonly testId?: string;
  readonly altText?: string;
  readonly title?: string;
}

export type LocatorStrategy =
  | { readonly kind: 'role'; readonly role: string; readonly name?: string | RegExp }
  | { readonly kind: 'label'; readonly text: string }
  | { readonly kind: 'placeholder'; readonly text: string }
  | { readonly kind: 'text'; readonly text: string }
  | { readonly kind: 'testId'; readonly id: string }
  | { readonly kind: 'altText'; readonly text: string }
  | { readonly kind: 'title'; readonly text: string };

export interface LocatorLike {
  count(): Promise<number>;
}

/** Minimal Playwright `Page` surface for locator lookups. */
export interface QueryablePage {
  getByRole(role: string, opts?: { name?: string | RegExp }): LocatorLike;
  getByLabel(text: string | RegExp): LocatorLike;
  getByPlaceholder(text: string | RegExp): LocatorLike;
  getByText(text: string | RegExp): LocatorLike;
  getByTestId(id: string | RegExp): LocatorLike;
  getByAltText(text: string | RegExp): LocatorLike;
  getByTitle(text: string | RegExp): LocatorLike;
}

export interface BestLocatorResult {
  readonly locator: LocatorLike;
  readonly strategy: LocatorStrategy;
}

function strategiesFor(target: ElementTarget): LocatorStrategy[] {
  const tries: LocatorStrategy[] = [];
  if (target.role !== undefined) {
    tries.push(
      target.accessibleName !== undefined
        ? { kind: 'role', role: target.role, name: target.accessibleName }
        : { kind: 'role', role: target.role },
    );
  }
  if (target.label !== undefined) tries.push({ kind: 'label', text: target.label });
  if (target.placeholder !== undefined) {
    tries.push({ kind: 'placeholder', text: target.placeholder });
  }
  if (target.text !== undefined) tries.push({ kind: 'text', text: target.text });
  if (target.testId !== undefined) tries.push({ kind: 'testId', id: target.testId });
  if (target.altText !== undefined) tries.push({ kind: 'altText', text: target.altText });
  if (target.title !== undefined) tries.push({ kind: 'title', text: target.title });
  return tries;
}

function applyStrategy(page: QueryablePage, strategy: LocatorStrategy): LocatorLike {
  switch (strategy.kind) {
    case 'role':
      return strategy.name !== undefined
        ? page.getByRole(strategy.role, { name: strategy.name })
        : page.getByRole(strategy.role);
    case 'label':
      return page.getByLabel(strategy.text);
    case 'placeholder':
      return page.getByPlaceholder(strategy.text);
    case 'text':
      return page.getByText(strategy.text);
    case 'testId':
      return page.getByTestId(strategy.id);
    case 'altText':
      return page.getByAltText(strategy.text);
    case 'title':
      return page.getByTitle(strategy.text);
  }
}

/**
 * Try the strategy chain in order; return the first strategy whose
 * locator matches exactly one element. Returns `null` when no strategy
 * yields a unique match — the caller (Generator / Healer) decides
 * whether to fall back to a brittle CSS selector or fail the spec
 * outright.
 */
export async function bestLocator(
  page: QueryablePage,
  target: ElementTarget,
): Promise<BestLocatorResult | null> {
  for (const strategy of strategiesFor(target)) {
    const locator = applyStrategy(page, strategy);
    let count: number;
    try {
      count = await locator.count();
    } catch {
      continue;
    }
    if (count === 1) return { locator, strategy };
  }
  return null;
}

/** Render a `LocatorStrategy` back to its Playwright source form. */
export function renderStrategy(strategy: LocatorStrategy): string {
  switch (strategy.kind) {
    case 'role':
      return strategy.name !== undefined
        ? `page.getByRole(${q(strategy.role)}, { name: ${renderNameArg(strategy.name)} })`
        : `page.getByRole(${q(strategy.role)})`;
    case 'label':
      return `page.getByLabel(${q(strategy.text)})`;
    case 'placeholder':
      return `page.getByPlaceholder(${q(strategy.text)})`;
    case 'text':
      return `page.getByText(${q(strategy.text)})`;
    case 'testId':
      return `page.getByTestId(${q(strategy.id)})`;
    case 'altText':
      return `page.getByAltText(${q(strategy.text)})`;
    case 'title':
      return `page.getByTitle(${q(strategy.text)})`;
  }
}

function q(s: string): string {
  return JSON.stringify(s);
}

function renderNameArg(name: string | RegExp): string {
  return name instanceof RegExp ? name.toString() : q(name);
}

// ---------------------------------------------------------------------
// describeLocator
// ---------------------------------------------------------------------

export interface LocatorDescriptor {
  readonly role: string | null;
  readonly accessibleName: string | null;
  readonly text: string | null;
  readonly landmarks: readonly string[];
  readonly tagName: string | null;
}

/**
 * `EvaluableLocator` is the subset of `Locator` we need for healing
 * descriptors. Playwright's real `Locator.evaluate(fn)` runs `fn` in
 * the browser; tests fake it with an in-process function.
 */
export interface EvaluableLocator {
  evaluate<R>(fn: (el: Element) => R): Promise<R>;
}

/**
 * Capture the descriptor used by the Healer () when proposing
 * locator repairs. Includes role, accessible name, visible text,
 * surrounding ARIA landmarks (parents with role attributes), and
 * `tagName`. All fields default to `null` when missing so the
 * descriptor is forward-compatible.
 */
export async function describeLocator(locator: EvaluableLocator): Promise<LocatorDescriptor> {
  return await locator.evaluate((el) => {
    const tagName = el.tagName.toLowerCase();
    const role = el.getAttribute('role');
    const accessibleName =
      el.getAttribute('aria-label') ??
      (el.tagName === 'IMG' ? el.getAttribute('alt') : null) ??
      ((el as HTMLElement).innerText ?? el.textContent ?? '').trim() ??
      null;
    const text = ((el as HTMLElement).innerText ?? el.textContent ?? '').trim() || null;
    const landmarks: string[] = [];
    let parent: Element | null = el.parentElement;
    while (parent !== null) {
      const parentRole = parent.getAttribute('role');
      if (parentRole !== null) landmarks.push(parentRole);
      parent = parent.parentElement;
    }
    return {
      role,
      accessibleName: accessibleName || null,
      text,
      landmarks,
      tagName,
    };
  });
}

// ---------------------------------------------------------------------
// Static brittleness audit
// ---------------------------------------------------------------------

export interface BrittlenessWarning {
  readonly line: number;
  readonly column: number;
  readonly message: string;
  readonly snippet: string;
}

export interface BrittlenessAudit {
  readonly warnings: readonly BrittlenessWarning[];
}

/**
 * Brittle CSS-locator patterns we always warn about. Each entry is
 * checked against the *argument string* of `page.locator(...)` /
 * `page.$(...)` calls.
 */
const BRITTLE_PATTERNS: { regex: RegExp; reason: string }[] = [
  {
    regex: /:nth-(?:of-type|child)\s*\(/i,
    reason: 'positional `:nth-of-type`/`:nth-child` selectors break when the DOM order changes',
  },
  {
    regex: /^xpath=/i,
    reason: 'raw XPath selectors are brittle; prefer semantic getByRole/getByLabel',
  },
  {
    regex: /^\/\//,
    reason: 'XPath shortcut (`//...`) is brittle; prefer semantic locators',
  },
  {
    regex: /^css=/i,
    reason: 'raw CSS selectors bypass semantic locator strategies',
  },
  {
    regex: /\bdiv\s*>\s*div\s*>\s*div/i,
    reason: 'deeply nested div selectors are brittle; prefer semantic landmarks',
  },
  {
    regex: /\[class\^=|\[class\*=/i,
    reason: 'class-prefix matchers break on CSS-in-JS hash changes',
  },
];

const SEMANTIC_METHODS = new Set([
  'getByRole',
  'getByLabel',
  'getByPlaceholder',
  'getByText',
  'getByTestId',
  'getByAltText',
  'getByTitle',
]);

/**
 * Audit a TypeScript spec source for brittle locator patterns.
 * Returns a list of warnings with line/column anchors. Uses ts-morph
 * for AST traversal so we catch `page.locator(...)` / `page.$(...)` /
 * `page.$$(...)` and chained accessors. the engineering guidelines
 * locators unless no semantic option exists; we report and leave the
 * call-site decision to the human reviewer.
 */
export function auditLocatorBrittleness(spec: string): BrittlenessAudit {
  const project = new Project({
    useInMemoryFileSystem: true,
    compilerOptions: { allowJs: true, target: 99 },
  });
  const file = project.createSourceFile('spec.ts', spec, { overwrite: true });
  const warnings: BrittlenessWarning[] = [];

  const calls = file.getDescendantsOfKind(SyntaxKind.CallExpression);
  for (const call of calls) {
    const expr = call.getExpression();
    if (!expr.isKind(SyntaxKind.PropertyAccessExpression)) continue;
    const method = expr.asKindOrThrow(SyntaxKind.PropertyAccessExpression).getName();
    const isRawSelector = method === 'locator' || method === '$' || method === '$$';
    if (!isRawSelector) continue;

    const args = call.getArguments();
    if (args.length === 0) continue;
    const first = args[0];
    if (first === undefined) continue;
    if (
      !first.isKind(SyntaxKind.StringLiteral) &&
      !first.isKind(SyntaxKind.NoSubstitutionTemplateLiteral)
    ) {
      continue;
    }
    const literal = first
      .asKindOrThrow(
        first.isKind(SyntaxKind.StringLiteral)
          ? SyntaxKind.StringLiteral
          : SyntaxKind.NoSubstitutionTemplateLiteral,
      )
      .getLiteralValue();

    for (const { regex, reason } of BRITTLE_PATTERNS) {
      if (regex.test(literal)) {
        const { line, column } = call.getSourceFile().getLineAndColumnAtPos(first.getPos());
        warnings.push({
          line,
          column,
          message: `${method}(${JSON.stringify(literal)}) — ${reason}`,
          snippet: call.getText(),
        });
        break;
      }
    }
  }

  // Bonus: count call-sites that use ONLY a raw selector and never any
  // semantic helper. Useful for the Generator's "did this spec ever
  // try the semantic path?" check.
  if (calls.length > 0) {
    let semanticUses = 0;
    let rawUses = 0;
    for (const call of calls) {
      const expr = call.getExpression();
      if (!expr.isKind(SyntaxKind.PropertyAccessExpression)) continue;
      const method = expr.asKindOrThrow(SyntaxKind.PropertyAccessExpression).getName();
      if (SEMANTIC_METHODS.has(method)) semanticUses += 1;
      if (method === 'locator' || method === '$' || method === '$$') rawUses += 1;
    }
    if (rawUses > 0 && semanticUses === 0) {
      warnings.push({
        line: 1,
        column: 1,
        message:
          'spec uses raw selectors but no semantic locator (getByRole / getByLabel / …); prefer semantic locators wherever possible',
        snippet: '',
      });
    }
  }

  return { warnings };
}
