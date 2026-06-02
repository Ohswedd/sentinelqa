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

// --------------------------------------------------------------------------- //
// Recorder tab (v1.11.0, phase 41)
// --------------------------------------------------------------------------- //

function setRecorderStatus(message: string, kind: 'ok' | 'error' | 'idle'): void {
  const node = document.getElementById('recorder-status');
  if (!node) return;
  node.textContent = message;
  node.className = 'status' + (kind === 'idle' ? '' : ' ' + kind);
}

async function injectAndStartRecording(name: string, priority: string): Promise<void> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    setRecorderStatus('No active tab.', 'error');
    return;
  }
  // Push the recorder script into the page and immediately call start.
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    files: ['dist/recorder.js'],
  });
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: (n: string, p: string) => {
      const w = window as unknown as {
        __sentinelqaRecorder?: {
          startRecording: (n: string, p: 'p0' | 'p1' | 'p2' | 'p3') => void;
        };
      };
      w.__sentinelqaRecorder?.startRecording(n, p as 'p0' | 'p1' | 'p2' | 'p3');
    },
    args: [name, priority],
  });
}

async function stopAndCollectRecording(): Promise<unknown> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    return null;
  }
  const [result] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => {
      const w = window as unknown as {
        __sentinelqaRecorder?: { stopRecording: () => unknown };
      };
      return w.__sentinelqaRecorder?.stopRecording() ?? null;
    },
  });
  return result?.result ?? null;
}

function downloadTrace(trace: unknown, name: string): void {
  const json = JSON.stringify(trace, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const safeName = (name || 'recording').replace(/[^A-Za-z0-9_-]+/g, '-');
  const link = document.createElement('a');
  link.href = url;
  link.download = `${safeName}.trace.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

async function onRecordStart(): Promise<void> {
  const nameInput = document.getElementById('recording-name') as HTMLInputElement;
  const prioritySelect = document.getElementById('recording-priority') as HTMLSelectElement;
  const startBtn = document.getElementById('record-start') as HTMLButtonElement;
  const stopBtn = document.getElementById('record-stop') as HTMLButtonElement;
  const name = (nameInput.value || 'recording').trim();
  const priority = prioritySelect.value;
  try {
    await injectAndStartRecording(name, priority);
    startBtn.disabled = true;
    stopBtn.disabled = false;
    setRecorderStatus(
      `Recording '${name}' (${priority}). Drive the flow in the active tab, then click Stop.`,
      'ok',
    );
  } catch (err) {
    setRecorderStatus(
      'Could not start recording: ' + String(err instanceof Error ? err.message : err),
      'error',
    );
  }
}

async function onRecordStop(): Promise<void> {
  const nameInput = document.getElementById('recording-name') as HTMLInputElement;
  const startBtn = document.getElementById('record-start') as HTMLButtonElement;
  const stopBtn = document.getElementById('record-stop') as HTMLButtonElement;
  try {
    const trace = await stopAndCollectRecording();
    if (!trace) {
      setRecorderStatus('No trace returned from the page.', 'error');
      return;
    }
    downloadTrace(trace, nameInput.value);
    setRecorderStatus('Trace downloaded. Feed it to `sentinel record import <file.json>`.', 'ok');
  } catch (err) {
    setRecorderStatus(
      'Could not stop recording: ' + String(err instanceof Error ? err.message : err),
      'error',
    );
  } finally {
    startBtn.disabled = false;
    stopBtn.disabled = true;
  }
}

function setupTabs(): void {
  const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>('.tab-button'));
  const panels = Array.from(document.querySelectorAll<HTMLElement>('.panel'));
  for (const btn of buttons) {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('aria-controls');
      for (const b of buttons) {
        b.setAttribute('aria-selected', b === btn ? 'true' : 'false');
      }
      for (const p of panels) {
        p.setAttribute('aria-hidden', p.id === targetId ? 'false' : 'true');
      }
    });
  }
}

async function init(): Promise<void> {
  const urlInput = document.getElementById('url') as HTMLInputElement;
  const url = await getActiveTabUrl();
  if (url) urlInput.value = url;
  await restoreSettings();
  const auditBtn = document.getElementById('audit') as HTMLButtonElement;
  auditBtn.addEventListener('click', () => {
    void runAudit();
  });
  setupTabs();
  document.getElementById('record-start')?.addEventListener('click', () => {
    void onRecordStart();
  });
  document.getElementById('record-stop')?.addEventListener('click', () => {
    void onRecordStop();
  });
}

void init();
