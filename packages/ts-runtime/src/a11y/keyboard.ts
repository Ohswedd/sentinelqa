// keyboard navigation + focus checks.
// the engineering guidelines: outputs always say "Automated accessibility check found"
// — they never make a full-compliance claim.

import type { KeyboardIssue } from './types.js';

export interface FocusSample {
  readonly selector: string;
  readonly visible: boolean;
  readonly tagName: string;
  readonly tabIndex: number;
}

export interface KeyboardWalkResult {
  readonly samples: readonly FocusSample[];
  readonly issues: readonly KeyboardIssue[];
}

/**
 * Tab through `max` focusable elements, recording focus order and
 * focus-visible state. The walk uses `page.keyboard.press('Tab')` and
 * reads `document.activeElement` between steps.
 *
 * The function is pure-ish: the caller injects `page` (or a stub).
 * Tests use the in-process stub in `__tests__/keyboard.test.ts`.
 */
export async function walkFocus(
  page: KeyboardPageLike,
  opts: { max?: number } = {},
): Promise<KeyboardWalkResult> {
  const max = opts.max ?? 200;
  const samples: FocusSample[] = [];
  const seen = new Set<string>();
  for (let i = 0; i < max; i += 1) {
    await page.keyboard.press('Tab');
    const sample = await page.evaluate(() => {
      const active = document.activeElement;
      if (!active || active === document.body) return null;
      const sel =
        (active as HTMLElement).id !== ''
          ? `#${(active as HTMLElement).id}`
          : active.tagName.toLowerCase() +
            ((active as HTMLElement).className
              ? '.' + (active as HTMLElement).className.split(/\s+/).join('.')
              : '');
      const cs = window.getComputedStyle(active);
      const visible =
        cs.outlineStyle !== 'none' || cs.boxShadow !== 'none' || cs.borderStyle !== 'none';
      return {
        selector: sel,
        visible,
        tagName: active.tagName.toLowerCase(),
        tabIndex: (active as HTMLElement).tabIndex ?? 0,
      } satisfies FocusSample;
    });
    if (sample === null) break;
    if (seen.has(sample.selector)) break;
    seen.add(sample.selector);
    samples.push(sample);
  }
  return {
    samples,
    issues: deriveKeyboardIssues(samples),
  };
}

/**
 * Apply the keyboard policy to a focus walk: every focusable element
 * must have a visible focus indicator; `tabIndex > 0` is reported as
 * a navigation issue because it disrupts the natural tab order.
 */
export function deriveKeyboardIssues(samples: readonly FocusSample[]): KeyboardIssue[] {
  const issues: KeyboardIssue[] = [];
  for (const s of samples) {
    if (!s.visible) {
      issues.push({
        category: 'focus-visible',
        selector: s.selector,
        description: `Automated accessibility check found ${s.tagName} without a visible focus indicator.`,
      });
    }
    if (s.tabIndex > 0) {
      issues.push({
        category: 'keyboard-navigation',
        selector: s.selector,
        description: `Automated accessibility check found tabindex=${s.tabIndex} (positive tabindex breaks natural tab order).`,
      });
    }
  }
  return issues;
}

/**
 * Detect a modal focus trap. When `modalOpen` is true and the user
 * cannot escape via Tab/Escape the modal is trapping focus.
 */
export function detectFocusTrap(args: {
  modalOpen: boolean;
  modalFocusables: number;
  canEscape: boolean;
}): KeyboardIssue | null {
  if (!args.modalOpen) return null;
  if (args.modalFocusables <= 0) return null;
  if (args.canEscape) return null;
  return {
    category: 'focus-trap',
    selector: "[role='dialog'], .modal, [aria-modal='true']",
    description:
      'Automated accessibility check found a modal that traps focus: focus cannot escape via Tab or Escape.',
  };
}

export interface KeyboardPageLike {
  readonly keyboard: { press(key: string): Promise<void> };
  evaluate<T>(fn: () => T | Promise<T>): Promise<T>;
}
