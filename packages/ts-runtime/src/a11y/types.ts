// Phase 11 (PRD §10.4, ADR-0016) — typed accessibility records.
//
// These types are the TS-side mirror of `modules/accessibility/models.py`.
// The wire format (one JSON file per route under <run-dir>/a11y/) is
// locked under ADR-0016 §3.

export type AxeImpact = 'critical' | 'serious' | 'moderate' | 'minor';
export type KeyboardCategory = 'keyboard-navigation' | 'focus-trap' | 'focus-visible';
export type LandmarkCategory = 'missing-landmark' | 'duplicate-landmark';

export interface AxeNode {
  readonly target: readonly string[];
  readonly html: string;
  readonly failureSummary: string;
}

export interface AxeViolation {
  readonly rule_id: string;
  readonly impact: AxeImpact;
  readonly help: string;
  readonly helpUrl: string;
  readonly description: string;
  readonly tags: readonly string[];
  readonly nodes: readonly AxeNode[];
  readonly experimental: boolean;
}

export interface KeyboardIssue {
  readonly category: KeyboardCategory;
  readonly selector: string;
  readonly description: string;
}

export interface LandmarkIssue {
  readonly category: LandmarkCategory;
  readonly landmark: string;
  readonly description: string;
}

export interface AccessibleNameIssue {
  readonly selector: string;
  readonly role: string;
  readonly description: string;
}

export interface A11yPageResult {
  readonly route: string;
  readonly url: string;
  readonly fetched_at: string;
  readonly axe_violations: readonly AxeViolation[];
  readonly keyboard_issues: readonly KeyboardIssue[];
  readonly landmark_issues: readonly LandmarkIssue[];
  readonly accessible_name_issues: readonly AccessibleNameIssue[];
  readonly duration_ms: number;
  readonly schema_version: string;
  readonly error?: string | null;
}

export interface A11yRunOutcome {
  readonly pages: readonly A11yPageResult[];
  readonly incomplete: boolean;
}

export const A11Y_RESULT_SCHEMA_VERSION = '1';
