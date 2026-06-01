// accessible-name check.
// Mirrors `modules/accessibility/checks/sr_names.py`: every interactive
// element must produce a computable accessible name. Placeholders are
// NOT a sufficient fallback because they
// disappear on input.

import type { AccessibleNameIssue } from './types.js';

export const INTERACTIVE_ROLES: ReadonlySet<string> = new Set([
  'button',
  'link',
  'textbox',
  'combobox',
  'checkbox',
  'radio',
  'switch',
  'menuitem',
]);

export interface ElementSample {
  readonly role: string;
  readonly selector: string;
  readonly ariaLabel: string;
  readonly ariaLabelledbyText: string;
  readonly labelText: string;
  readonly visibleText: string;
  readonly title: string;
  readonly placeholder: string;
}

export function hasAccessibleName(el: ElementSample): boolean {
  return Boolean(
    el.ariaLabelledbyText?.trim() ||
      el.ariaLabel?.trim() ||
      el.labelText?.trim() ||
      el.visibleText?.trim() ||
      el.title?.trim(),
  );
}

export function detectMissingAccessibleNames(
  elements: readonly ElementSample[],
): AccessibleNameIssue[] {
  const issues: AccessibleNameIssue[] = [];
  for (const el of elements) {
    if (!INTERACTIVE_ROLES.has(el.role)) continue;
    if (hasAccessibleName(el)) continue;
    issues.push({
      selector: el.selector,
      role: el.role,
      description: `Automated accessibility check found ${el.role} element with no computable accessible name; screen readers cannot announce it.`,
    });
  }
  return issues;
}

export interface SrNamesPageLike {
  evaluate<T>(fn: () => T | Promise<T>): Promise<T>;
}

export async function readInteractiveSamples(
  page: SrNamesPageLike,
): Promise<readonly ElementSample[]> {
  return await page.evaluate(() => {
    const roleOf = (el: Element): string => {
      const explicit = el.getAttribute('role');
      if (explicit) return explicit;
      const tag = el.tagName.toLowerCase();
      if (tag === 'button') return 'button';
      if (tag === 'a' && el.hasAttribute('href')) return 'link';
      if (tag === 'input') {
        const type = (el.getAttribute('type') ?? 'text').toLowerCase();
        if (type === 'checkbox') return 'checkbox';
        if (type === 'radio') return 'radio';
        if (type === 'button' || type === 'submit') return 'button';
        return 'textbox';
      }
      if (tag === 'select') return 'combobox';
      if (tag === 'textarea') return 'textbox';
      return '';
    };
    const labelText = (el: Element): string => {
      if (!(el instanceof HTMLElement)) return '';
      const id = el.id;
      if (id) {
        const lbl = document.querySelector(`label[for="${id}"]`);
        if (lbl !== null) return lbl.textContent?.trim() ?? '';
      }
      const parent = el.closest('label');
      return parent ? (parent.textContent?.trim() ?? '') : '';
    };
    const out: ElementSample[] = [];
    const candidates = document.querySelectorAll(
      'button, a[href], input, select, textarea, [role]',
    );
    candidates.forEach((el) => {
      const role = roleOf(el);
      if (!role) return;
      const selector =
        (el as HTMLElement).id !== '' ? `#${(el as HTMLElement).id}` : el.tagName.toLowerCase();
      const ariaLabelledby = el.getAttribute('aria-labelledby');
      let ariaLabelledbyText = '';
      if (ariaLabelledby) {
        const parts = ariaLabelledby
          .split(/\s+/)
          .map((id) => document.getElementById(id)?.textContent?.trim() ?? '')
          .filter(Boolean);
        ariaLabelledbyText = parts.join(' ');
      }
      out.push({
        role,
        selector,
        ariaLabel: el.getAttribute('aria-label') ?? '',
        ariaLabelledbyText,
        labelText: labelText(el),
        visibleText: (el.textContent ?? '').trim(),
        title: el.getAttribute('title') ?? '',
        placeholder: el.getAttribute('placeholder') ?? '',
      });
    });
    return out;
  });
}
