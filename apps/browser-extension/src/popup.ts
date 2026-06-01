// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 SentinelQA contributors.

import { validateLoopbackTarget } from './loopback';

const STORAGE_KEYS = {
  host: 'sentinelqa.mcp.host',
  port: 'sentinelqa.mcp.port',
} as const;

async function getActiveTabUrl(): Promise<string | null> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab?.url ?? null;
}

async function restoreSettings(): Promise<void> {
  const stored = await chrome.storage.local.get([STORAGE_KEYS.host, STORAGE_KEYS.port]);
  const hostInput = document.getElementById('host') as HTMLInputElement;
  const portInput = document.getElementById('port') as HTMLInputElement;
  if (stored[STORAGE_KEYS.host] && typeof stored[STORAGE_KEYS.host] === 'string') {
    hostInput.value = stored[STORAGE_KEYS.host] as string;
  }
  if (stored[STORAGE_KEYS.port] && typeof stored[STORAGE_KEYS.port] === 'number') {
    portInput.value = String(stored[STORAGE_KEYS.port]);
  }
}

async function persistSettings(host: string, port: number): Promise<void> {
  await chrome.storage.local.set({ [STORAGE_KEYS.host]: host, [STORAGE_KEYS.port]: port });
}

function setStatus(message: string, kind: 'ok' | 'error' | 'idle'): void {
  const node = document.getElementById('status');
  if (!node) return;
  node.textContent = message;
  node.className = 'status' + (kind === 'idle' ? '' : ' ' + kind);
}

async function runAudit(): Promise<void> {
  const urlInput = document.getElementById('url') as HTMLInputElement;
  const hostInput = document.getElementById('host') as HTMLInputElement;
  const portInput = document.getElementById('port') as HTMLInputElement;
  const button = document.getElementById('audit') as HTMLButtonElement;

  const targetUrl = urlInput.value.trim();
  const host = hostInput.value.trim();
  const port = Number.parseInt(portInput.value, 10);

  const validation = validateLoopbackTarget(host, port);
  if (!validation.ok) {
    setStatus(`Refusing: ${validation.reason}. Only loopback hosts are accepted.`, 'error');
    return;
  }

  await persistSettings(host, port);
  button.disabled = true;
  setStatus('Posting to ' + validation.normalised + ' …', 'idle');

  try {
    const response = await fetch(`${validation.normalised}/rpc`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: Date.now(),
        method: 'sentinel.audit',
        params: { url: targetUrl },
      }),
    });
    if (!response.ok) {
      setStatus(`Server responded ${response.status} ${response.statusText}.`, 'error');
      return;
    }
    const body = (await response.json()) as { result?: { run_id?: string; status?: string } };
    if (body.result?.run_id) {
      setStatus(
        `Run ${body.result.run_id} → ${body.result.status ?? 'queued'}. ` +
          'Open the latest report from your terminal: sentinel report --latest.',
        'ok',
      );
    } else {
      setStatus('Server responded but no run_id was returned. Check the local MCP log.', 'error');
    }
  } catch (err) {
    setStatus(
      `Could not reach the local MCP server. Is \`sentinel mcp --http --port ${port}\` running?\n\n` +
        String(err instanceof Error ? err.message : err),
      'error',
    );
  } finally {
    button.disabled = false;
  }
}

async function init(): Promise<void> {
  const urlInput = document.getElementById('url') as HTMLInputElement;
  const url = await getActiveTabUrl();
  if (url) urlInput.value = url;
  await restoreSettings();
  const button = document.getElementById('audit') as HTMLButtonElement;
  button.addEventListener('click', () => {
    void runAudit();
  });
}

void init();
