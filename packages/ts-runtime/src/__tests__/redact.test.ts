import { describe, expect, it } from 'vitest';

import { loadRedactionRules, redact, redactHeaders, redactString, redactUrl } from '../redact.js';

describe('redact.ts — rule loading', () => {
  it('loads the shared ruleset JSON from disk', () => {
    const rules = loadRedactionRules();
    expect(rules.schema_version).toMatch(/^\d+\.\d+\.\d+/);
    expect(rules.secret_key_names.length).toBeGreaterThan(10);
    expect(rules.value_rules.length).toBeGreaterThan(5);
    expect(rules.redacted_template).toBe('[REDACTED:{category}]');
  });
});

describe('redact.ts — value rules', () => {
  it('replaces bearer tokens', () => {
    expect(redactString('Authorization: Bearer abc.DEF-ghi_jklmno0123456789')).toBe(
      'Authorization: [REDACTED:bearer_token]',
    );
  });

  it('replaces JWTs', () => {
    expect(
      redactString('token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.deadbeef-cafebabe1234'),
    ).toBe('token=[REDACTED:jwt]');
  });

  it('replaces AWS access-key IDs', () => {
    expect(redactString('AKIAIOSFODNN7EXAMPLE in logs')).toBe(
      '[REDACTED:aws_access_key_id] in logs',
    );
  });

  it('replaces a high-entropy generic token', () => {
    const out = redactString('session=Hb3KsP9w-jK4VqL0nx7Ze1QmRtUvY2Cd');
    expect(out).toContain('[REDACTED:high_entropy_token]');
    expect(out).not.toContain('Hb3KsP9w-jK4VqL0nx7Ze1QmRtUvY2Cd');
  });

  it('passes safe text through unchanged', () => {
    expect(redactString('the quick brown fox')).toBe('the quick brown fox');
  });
});

describe('redact.ts — recursive redact()', () => {
  it('redacts secret-named keys', () => {
    const out = redact({
      username: 'alice',
      password: 'hunter2',
      Authorization: 'Bearer token-xyz-very-long-token-for-test-123',
    }) as Record<string, string>;
    expect(out['username']).toBe('alice');
    expect(out['password']).toBe('[REDACTED:password]');
    expect(out['Authorization']).toBe('[REDACTED:authorization]');
  });

  it('walks lists and nested dicts', () => {
    const out = redact({ items: [{ api_key: '12345abcdef' }, { name: 'ok' }] }) as {
      items: Record<string, string>[];
    };
    expect(out.items[0]?.['api_key']).toBe('[REDACTED:api_key]');
    expect(out.items[1]?.['name']).toBe('ok');
  });

  it('preserves empty-string secret values (sentinel mirrors Python)', () => {
    const out = redact({ token: '' }) as Record<string, string>;
    expect(out['token']).toBe('');
  });

  it('caps recursion depth', () => {
    interface Node {
      next?: Node;
    }
    const deep: Node = {};
    let cur: Node = deep;
    for (let i = 0; i < 20; i++) {
      const node: Node = {};
      cur.next = node;
      cur = node;
    }
    const out = redact(deep) as Record<string, unknown>;
    expect(JSON.stringify(out)).toContain('[REDACTED:depth_limit]');
  });
});

describe('redact.ts — header redaction', () => {
  it('redacts authorization regardless of header case', () => {
    const out = redactHeaders({
      Authorization: 'Bearer xyz',
      'content-type': 'application/json',
    });
    expect(out['Authorization']).toBe('[REDACTED:authorization]');
    expect(out['content-type']).toBe('application/json');
  });

  it('redacts Cookie and Set-Cookie', () => {
    const out = redactHeaders({
      Cookie: 'sid=abc',
      'Set-Cookie': 'sid=abc; Path=/',
    });
    expect(out['Cookie']).toBe('[REDACTED:cookie]');
    expect(out['Set-Cookie']).toBe('[REDACTED:set-cookie]');
  });
});

describe('redact.ts — URL redaction', () => {
  it('strips userinfo', () => {
    const out = redactUrl('https://alice:hunter2@example.com/path');
    expect(out).not.toContain('alice');
    expect(out).not.toContain('hunter2');
    expect(out).toContain('[REDACTED:userinfo]@example.com');
  });

  it('masks secret-shaped query keys', () => {
    const out = redactUrl('https://example.com/?token=deadbeef&q=hello');
    expect(out).toContain('token=');
    expect(out).not.toContain('deadbeef');
    expect(out).toContain('REDACTED');
    expect(out).toContain('q=hello');
  });

  it('returns non-URL input unchanged', () => {
    expect(redactUrl('not a url')).toBe('not a url');
  });
});
