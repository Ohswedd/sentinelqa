// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 SentinelQA contributors.
//
// In-browser recorder content script (v1.10.0, phase 40).
//
// Runs in the page context, listens for high-level user interactions
// (click, fill, navigate), and emits the JSON trace format that
// `sentinel record import` consumes:
//
//   {
//     "schema_version": "1",
//     "name": "<recording-name>",
//     "base_url": "<origin>",
//     "priority": "p2",
//     "steps": [
//       {"action": "navigate", "url": "..."},
//       {"action": "click",    "selector": "..."},
//       {"action": "fill",     "selector": "...", "value": "..."},
//       ...
//     ]
//   }
//
// The recorder is opt-in: only active when chrome.storage.local has
// { sentinelqaRecording: true }. Stop button writes the trace to
// chrome.storage.local under sentinelqaTrace; the popup downloads it
// from there.
//
// Selector synthesis prefers stable hooks (`#id`, `[data-testid]`,
// `[aria-label]`) before falling back to a positional CSS path.

const SCHEMA_VERSION = '1';

export interface RecordedStep {
  readonly action:
    | 'navigate'
    | 'click'
    | 'fill'
    | 'press'
    | 'select'
    | 'check'
    | 'uncheck'
    | 'hover'
    | 'wait_for'
    | 'expect';
  readonly selector?: string;
  readonly url?: string;
  readonly value?: string;
  readonly key?: string;
}

export interface RecordingTrace {
  readonly schema_version: typeof SCHEMA_VERSION;
  readonly name: string;
  readonly base_url: string;
  readonly priority: 'p0' | 'p1' | 'p2' | 'p3';
  readonly steps: readonly RecordedStep[];
}

interface RecorderState {
  active: boolean;
  name: string;
  priority: 'p0' | 'p1' | 'p2' | 'p3';
  steps: RecordedStep[];
}

const state: RecorderState = {
  active: false,
  name: 'unnamed-recording',
  priority: 'p2',
  steps: [],
};

function safeCssEscape(value: string): string {
  // jsdom lacks the CSS global in some configs; the spec algorithm is
  // small enough to inline for our id / attribute use cases.
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
    return CSS.escape(value);
  }
  return value.replace(/([^a-zA-Z0-9_-])/g, '\\$1');
}

const SELECTOR_PRIORITY: readonly ((el: Element) => string | null)[] = [
  (el) => (el.id ? `#${safeCssEscape(el.id)}` : null),
  (el) => {
    const testId = el.getAttribute('data-testid');
    return testId ? `[data-testid="${escapeAttr(testId)}"]` : null;
  },
  (el) => {
    const label = el.getAttribute('aria-label');
    return label ? `[aria-label="${escapeAttr(label)}"]` : null;
  },
  (el) => {
    const name = el.getAttribute('name');
    return name ? `[name="${escapeAttr(name)}"]` : null;
  },
];

function escapeAttr(value: string): string {
  return value.replace(/"/g, '\\"');
}

function synthesizeSelector(el: Element | null): string | null {
  if (!el) {
    return null;
  }
  for (const candidate of SELECTOR_PRIORITY) {
    const sel = candidate(el);
    if (sel) {
      return sel;
    }
  }
  const tag = el.tagName.toLowerCase();
  const parent = el.parentElement;
  if (!parent) {
    return tag;
  }
  const siblings = Array.from(parent.children).filter((c) => c.tagName === el.tagName);
  const index = siblings.indexOf(el) + 1;
  return `${tag}:nth-of-type(${index})`;
}

function appendStep(step: RecordedStep): void {
  if (!state.active) {
    return;
  }
  state.steps.push(step);
}

function onClick(event: MouseEvent): void {
  if (!state.active) {
    return;
  }
  const target = event.target as Element | null;
  const selector = synthesizeSelector(target);
  if (!selector) {
    return;
  }
  appendStep({ action: 'click', selector });
}

function onChange(event: Event): void {
  if (!state.active) {
    return;
  }
  const target = event.target as HTMLInputElement | HTMLSelectElement | null;
  if (!target) {
    return;
  }
  const selector = synthesizeSelector(target);
  if (!selector) {
    return;
  }
  if (target.tagName === 'SELECT') {
    appendStep({ action: 'select', selector, value: target.value });
    return;
  }
  if (target instanceof HTMLInputElement) {
    if (target.type === 'checkbox') {
      appendStep({
        action: target.checked ? 'check' : 'uncheck',
        selector,
      });
      return;
    }
    appendStep({ action: 'fill', selector, value: target.value });
    return;
  }
}

function onKeyDown(event: KeyboardEvent): void {
  if (!state.active) {
    return;
  }
  if (event.key !== 'Enter' && event.key !== 'Escape' && event.key !== 'Tab') {
    return;
  }
  const target = event.target as Element | null;
  const selector = synthesizeSelector(target);
  if (!selector) {
    return;
  }
  appendStep({ action: 'press', selector, key: event.key });
}

export function startRecording(name: string, priority: 'p0' | 'p1' | 'p2' | 'p3'): void {
  if (state.active) {
    return;
  }
  state.active = true;
  state.name = name || 'unnamed-recording';
  state.priority = priority;
  state.steps = [
    {
      action: 'navigate',
      url: window.location.href,
    },
  ];
  document.addEventListener('click', onClick, true);
  document.addEventListener('change', onChange, true);
  document.addEventListener('keydown', onKeyDown, true);
}

export function stopRecording(): RecordingTrace {
  if (!state.active) {
    return buildTrace();
  }
  document.removeEventListener('click', onClick, true);
  document.removeEventListener('change', onChange, true);
  document.removeEventListener('keydown', onKeyDown, true);
  state.active = false;
  return buildTrace();
}

export function buildTrace(): RecordingTrace {
  return {
    schema_version: SCHEMA_VERSION,
    name: state.name,
    base_url: window.location.origin,
    priority: state.priority,
    steps: [...state.steps],
  };
}

export function clearRecording(): void {
  state.active = false;
  state.steps = [];
}

// Test seam: callers can drive the recorder from tests by hand-firing events.
export const _internal = {
  state,
  synthesizeSelector,
};

// When loaded as a content script via chrome.scripting.executeScript, expose
// the recorder API on window so the popup can drive it from the extension
// context. Plain ESM imports also work; this is just the bridge.
if (typeof window !== 'undefined') {
  const w = window as unknown as {
    __sentinelqaRecorder?: {
      startRecording: typeof startRecording;
      stopRecording: typeof stopRecording;
      buildTrace: typeof buildTrace;
      clearRecording: typeof clearRecording;
    };
  };
  w.__sentinelqaRecorder = {
    startRecording,
    stopRecording,
    buildTrace,
    clearRecording,
  };
}
