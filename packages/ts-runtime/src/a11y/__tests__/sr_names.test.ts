import { describe, it, expect } from 'vitest';

import {
  detectMissingAccessibleNames,
  hasAccessibleName,
  type ElementSample,
} from '../sr_names.js';

const el = (overrides: Partial<ElementSample>): ElementSample => ({
  role: 'button',
  selector: '#x',
  ariaLabel: '',
  ariaLabelledbyText: '',
  labelText: '',
  visibleText: '',
  title: '',
  placeholder: '',
  ...overrides,
});

describe('hasAccessibleName', () => {
  it('accepts visible text', () => {
    expect(hasAccessibleName(el({ visibleText: 'Submit' }))).toBe(true);
  });
  it('accepts aria-label', () => {
    expect(hasAccessibleName(el({ ariaLabel: 'Close' }))).toBe(true);
  });
  it('accepts aria-labelledby chain', () => {
    expect(hasAccessibleName(el({ ariaLabelledbyText: 'Open menu' }))).toBe(true);
  });
  it('accepts label text', () => {
    expect(hasAccessibleName(el({ role: 'textbox', labelText: 'Email' }))).toBe(true);
  });
  it('accepts title as fallback', () => {
    expect(hasAccessibleName(el({ title: 'More info' }))).toBe(true);
  });
  it('does NOT accept placeholder alone', () => {
    expect(hasAccessibleName(el({ role: 'textbox', placeholder: 'Search' }))).toBe(false);
  });
});

describe('detectMissingAccessibleNames', () => {
  it('returns one issue per interactive element without a name', () => {
    const issues = detectMissingAccessibleNames([
      el({ role: 'button', selector: '#a' }),
      el({ role: 'link', selector: '#b', visibleText: 'Home' }),
      el({ role: 'presentation', selector: '#c' }),
    ]);
    expect(issues.map((i) => i.selector)).toEqual(['#a']);
  });

  it('returns nothing when every interactive element has a name', () => {
    const issues = detectMissingAccessibleNames([
      el({ role: 'button', ariaLabel: 'Close', selector: '#a' }),
    ]);
    expect(issues).toEqual([]);
  });
});
