import { describe, expect, it } from 'vitest';

import {
  auditLocatorBrittleness,
  bestLocator,
  describeLocator,
  renderStrategy,
} from '../locators.js';
import type { EvaluableLocator, LocatorLike, LocatorStrategy, QueryablePage } from '../locators.js';

interface StubLocator extends LocatorLike {
  hits: number;
}

function stub(hits: number): StubLocator {
  return {
    hits,
    count: () => Promise.resolve(hits),
  };
}

interface PageHits {
  role?: number;
  roleNamed?: number;
  label?: number;
  placeholder?: number;
  text?: number;
  testId?: number;
  altText?: number;
  title?: number;
}

function buildPage(hits: PageHits): QueryablePage {
  return {
    getByRole: (_role, opts) =>
      stub(opts?.name !== undefined ? (hits.roleNamed ?? 0) : (hits.role ?? 0)),
    getByLabel: () => stub(hits.label ?? 0),
    getByPlaceholder: () => stub(hits.placeholder ?? 0),
    getByText: () => stub(hits.text ?? 0),
    getByTestId: () => stub(hits.testId ?? 0),
    getByAltText: () => stub(hits.altText ?? 0),
    getByTitle: () => stub(hits.title ?? 0),
  };
}

describe('bestLocator', () => {
  it('returns getByRole when role+name yield exactly one match', async () => {
    const page = buildPage({ roleNamed: 1 });
    const result = await bestLocator(page, { role: 'button', accessibleName: /sign in/i });
    expect(result).not.toBeNull();
    expect(result!.strategy.kind).toBe('role');
  });

  it('falls through to label when role yields 0 or many matches', async () => {
    const page = buildPage({ role: 3, label: 1 });
    const result = await bestLocator(page, { role: 'button', label: 'Email' });
    expect(result).not.toBeNull();
    expect(result!.strategy.kind).toBe('label');
  });

  it('honors strategy order: placeholder over text over testId', async () => {
    const page = buildPage({ placeholder: 1, text: 1, testId: 1 });
    const result = await bestLocator(page, {
      placeholder: 'you@example.com',
      text: 'Email',
      testId: 'email-input',
    });
    expect(result!.strategy.kind).toBe('placeholder');
  });

  it('falls through to testId when no semantic options match', async () => {
    const page = buildPage({ testId: 1 });
    const result = await bestLocator(page, { testId: 'submit-button' });
    expect(result!.strategy.kind).toBe('testId');
  });

  it('returns null when no strategy yields a unique match', async () => {
    const page = buildPage({ role: 0, label: 0 });
    const result = await bestLocator(page, { role: 'button', label: 'Email' });
    expect(result).toBeNull();
  });

  it('skips strategies whose `count` throws', async () => {
    const page: QueryablePage = {
      getByRole: () => ({ count: () => Promise.reject(new Error('boom')) }),
      getByLabel: () => stub(1),
      getByPlaceholder: () => stub(0),
      getByText: () => stub(0),
      getByTestId: () => stub(0),
      getByAltText: () => stub(0),
      getByTitle: () => stub(0),
    };
    const result = await bestLocator(page, { role: 'button', label: 'Email' });
    expect(result!.strategy.kind).toBe('label');
  });
});

describe('renderStrategy', () => {
  it('renders getByRole with name regex', () => {
    const s: LocatorStrategy = { kind: 'role', role: 'button', name: /sign in/i };
    expect(renderStrategy(s)).toBe('page.getByRole("button", { name: /sign in/i })');
  });

  it('renders getByRole without name', () => {
    const s: LocatorStrategy = { kind: 'role', role: 'navigation' };
    expect(renderStrategy(s)).toBe('page.getByRole("navigation")');
  });

  it('renders getByLabel / getByTestId / getByText', () => {
    expect(renderStrategy({ kind: 'label', text: 'Email' })).toBe('page.getByLabel("Email")');
    expect(renderStrategy({ kind: 'testId', id: 'submit' })).toBe('page.getByTestId("submit")');
    expect(renderStrategy({ kind: 'text', text: 'Hello' })).toBe('page.getByText("Hello")');
  });
});

describe('describeLocator', () => {
  it('captures role, accessible name, text, landmarks, tagName', async () => {
    const fakeLocator: EvaluableLocator = {
      evaluate: (fn) => {
        // Build a minimal Element-shaped fake good enough for the
        // describeLocator function body.
        const mainAncestor = {
          tagName: 'MAIN',
          getAttribute: (k: string) => (k === 'role' ? 'main' : null),
          parentElement: null as Element | null,
        };
        const navAncestor = {
          tagName: 'NAV',
          getAttribute: (k: string) => (k === 'role' ? 'navigation' : null),
          parentElement: mainAncestor as unknown as Element,
        };
        const el = {
          tagName: 'BUTTON',
          getAttribute: (k: string) => {
            if (k === 'role') return 'button';
            if (k === 'aria-label') return 'Sign in';
            return null;
          },
          textContent: 'Sign in',
          innerText: 'Sign in',
          parentElement: navAncestor as unknown as Element,
        };
        return Promise.resolve(fn(el as unknown as Element));
      },
    };
    const desc = await describeLocator(fakeLocator);
    expect(desc.role).toBe('button');
    expect(desc.accessibleName).toBe('Sign in');
    expect(desc.tagName).toBe('button');
    expect(desc.landmarks).toEqual(['navigation', 'main']);
    expect(desc.text).toBe('Sign in');
  });
});

describe('auditLocatorBrittleness', () => {
  it('flags page.locator with :nth-of-type', () => {
    const spec = `
      import { test } from '@playwright/test';
      test('demo', async ({ page }) => {
        await page.locator('div:nth-of-type(3)').click();
      });
    `;
    const audit = auditLocatorBrittleness(spec);
    expect(audit.warnings.length).toBeGreaterThanOrEqual(1);
    expect(audit.warnings.some((w) => w.message.includes(':nth-of-type'))).toBe(true);
  });

  it('flags raw XPath selectors (xpath= prefix)', () => {
    const spec = `
      import { test } from '@playwright/test';
      test('x', async ({ page }) => {
        await page.locator('xpath=//div[@id="x"]').click();
      });
    `;
    const audit = auditLocatorBrittleness(spec);
    expect(audit.warnings.some((w) => w.message.includes('XPath'))).toBe(true);
  });

  it('flags deeply nested div > div > div selectors', () => {
    const spec = `
      import { test } from '@playwright/test';
      test('y', async ({ page }) => {
        await page.locator('div > div > div span').click();
      });
    `;
    const audit = auditLocatorBrittleness(spec);
    expect(audit.warnings.some((w) => w.message.includes('nested div'))).toBe(true);
  });

  it('warns when a spec uses only raw selectors with no semantic locator', () => {
    const spec = `
      import { test } from '@playwright/test';
      test('z', async ({ page }) => {
        await page.locator('#email').fill('a@b.com');
      });
    `;
    const audit = auditLocatorBrittleness(spec);
    expect(audit.warnings.some((w) => w.message.includes('no semantic locator'))).toBe(true);
  });

  it('does not warn on a clean semantic-only spec', () => {
    const spec = `
      import { test } from '@playwright/test';
      test('clean', async ({ page }) => {
        await page.getByRole('button', { name: /sign in/i }).click();
        await page.getByLabel('Email').fill('a@b.com');
      });
    `;
    const audit = auditLocatorBrittleness(spec);
    expect(audit.warnings).toEqual([]);
  });
});
