// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 SentinelQA contributors.

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { _internal, buildTrace, clearRecording, startRecording, stopRecording } from './recorder';

describe('recorder', () => {
  beforeEach(() => {
    clearRecording();
    document.body.innerHTML = '';
  });

  afterEach(() => {
    clearRecording();
  });

  it('emits the v1 schema envelope', () => {
    startRecording('checkout', 'p0');
    const trace = stopRecording();
    expect(trace.schema_version).toBe('1');
    expect(trace.name).toBe('checkout');
    expect(trace.priority).toBe('p0');
    expect(trace.base_url).toBe(window.location.origin);
  });

  it('records the navigate step on start', () => {
    startRecording('flow', 'p2');
    const trace = stopRecording();
    expect(trace.steps[0]).toEqual({
      action: 'navigate',
      url: window.location.href,
    });
  });

  it('captures clicks with the synthesized selector', () => {
    document.body.innerHTML = '<button id="go">Go</button>';
    startRecording('click-flow', 'p3');
    const btn = document.getElementById('go');
    btn?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    const trace = stopRecording();
    const click = trace.steps.find((s) => s.action === 'click');
    expect(click?.selector).toBe('#go');
  });

  it('prefers data-testid over tag fallback', () => {
    document.body.innerHTML = '<div data-testid="sentinel-target"></div>';
    startRecording('testid', 'p3');
    const div = document.querySelector('[data-testid="sentinel-target"]');
    div?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    const trace = stopRecording();
    const click = trace.steps.find((s) => s.action === 'click');
    expect(click?.selector).toBe('[data-testid="sentinel-target"]');
  });

  it('records fills on text inputs', () => {
    document.body.innerHTML = '<input id="email" />';
    startRecording('fill', 'p3');
    const input = document.getElementById('email') as HTMLInputElement;
    input.value = 'x@example.com';
    input.dispatchEvent(new Event('change', { bubbles: true }));
    const trace = stopRecording();
    const fill = trace.steps.find((s) => s.action === 'fill');
    expect(fill).toEqual({
      action: 'fill',
      selector: '#email',
      value: 'x@example.com',
    });
  });

  it('records check / uncheck on checkboxes', () => {
    document.body.innerHTML = '<input id="agree" type="checkbox" />';
    startRecording('check', 'p3');
    const cb = document.getElementById('agree') as HTMLInputElement;
    cb.checked = true;
    cb.dispatchEvent(new Event('change', { bubbles: true }));
    cb.checked = false;
    cb.dispatchEvent(new Event('change', { bubbles: true }));
    const trace = stopRecording();
    const checks = trace.steps.filter((s) => s.action === 'check' || s.action === 'uncheck');
    expect(checks.length).toBe(2);
    expect(checks[0].action).toBe('check');
    expect(checks[1].action).toBe('uncheck');
  });

  it('captures Enter key presses', () => {
    document.body.innerHTML = '<input id="search" />';
    startRecording('press', 'p3');
    const input = document.getElementById('search') as HTMLInputElement;
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    const trace = stopRecording();
    const press = trace.steps.find((s) => s.action === 'press');
    expect(press).toEqual({ action: 'press', selector: '#search', key: 'Enter' });
  });

  it('ignores events when not recording', () => {
    document.body.innerHTML = '<button id="x">x</button>';
    const btn = document.getElementById('x');
    btn?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    const trace = buildTrace();
    expect(trace.steps.length).toBe(0);
  });

  it('synthesizeSelector handles nested anonymous elements', () => {
    document.body.innerHTML = '<section><div></div><div></div></section>';
    const divs = document.querySelectorAll('section > div');
    expect(_internal.synthesizeSelector(divs[1])).toBe('div:nth-of-type(2)');
  });

  it('clearRecording wipes accumulated steps', () => {
    document.body.innerHTML = '<button id="go">x</button>';
    startRecording('flow', 'p3');
    document.getElementById('go')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    clearRecording();
    const trace = buildTrace();
    expect(trace.steps.length).toBe(0);
  });
});
