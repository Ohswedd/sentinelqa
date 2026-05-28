import { describe, it, expect } from 'vitest';

import { deriveKeyboardIssues, detectFocusTrap, walkFocus, type FocusSample } from '../keyboard.js';

const sample = (overrides: Partial<FocusSample>): FocusSample => ({
  selector: '#btn',
  visible: true,
  tagName: 'button',
  tabIndex: 0,
  ...overrides,
});

describe('detectFocusTrap', () => {
  it('returns a finding when a modal traps focus', () => {
    const issue = detectFocusTrap({ modalOpen: true, modalFocusables: 3, canEscape: false });
    expect(issue).not.toBeNull();
    expect(issue?.category).toBe('focus-trap');
  });

  it('returns null for a compliant modal', () => {
    expect(detectFocusTrap({ modalOpen: true, modalFocusables: 3, canEscape: true })).toBeNull();
  });

  it('returns null when no modal is open', () => {
    expect(detectFocusTrap({ modalOpen: false, modalFocusables: 3, canEscape: false })).toBeNull();
  });

  it('returns null when the modal has nothing focusable', () => {
    expect(detectFocusTrap({ modalOpen: true, modalFocusables: 0, canEscape: false })).toBeNull();
  });
});

describe('deriveKeyboardIssues', () => {
  it('flags elements without a visible focus indicator', () => {
    const issues = deriveKeyboardIssues([sample({ visible: false, selector: '#a' })]);
    expect(issues).toHaveLength(1);
    expect(issues[0]?.category).toBe('focus-visible');
  });

  it('flags positive tabindex as navigation issue', () => {
    const issues = deriveKeyboardIssues([sample({ tabIndex: 4, selector: '#a' })]);
    expect(issues.map((i) => i.category)).toContain('keyboard-navigation');
  });

  it('combines focus-visible + navigation issues per element', () => {
    const issues = deriveKeyboardIssues([sample({ visible: false, tabIndex: 4, selector: '#x' })]);
    expect(issues).toHaveLength(2);
  });

  it('returns an empty list for compliant elements', () => {
    expect(deriveKeyboardIssues([sample({})])).toEqual([]);
  });
});

describe('walkFocus', () => {
  it('stops when document.activeElement returns null', async () => {
    let presses = 0;
    const page = {
      keyboard: {
        press: async (_: string) => {
          presses += 1;
        },
      },
      evaluate: async <T>(_fn: () => T | Promise<T>): Promise<T> => null as unknown as T,
    };
    const result = await walkFocus(page, { max: 10 });
    expect(presses).toBe(1);
    expect(result.samples).toEqual([]);
  });

  it('stops when the same selector recurs', async () => {
    const samples = [
      sample({ selector: '#a' }),
      sample({ selector: '#b' }),
      sample({ selector: '#a' }), // recurrence → break
    ];
    let i = 0;
    const page = {
      keyboard: { press: async () => undefined },
      evaluate: async <T>(_fn: () => T | Promise<T>): Promise<T> => {
        const out = samples[i++];
        return (out ?? null) as unknown as T;
      },
    };
    const result = await walkFocus(page, { max: 10 });
    expect(result.samples.map((s) => s.selector)).toEqual(['#a', '#b']);
  });
});
