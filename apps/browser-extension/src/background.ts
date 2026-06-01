// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 SentinelQA contributors.
//
// MV3 background service worker. Intentionally minimal — the popup
// does the work. We only register an install-time log so users see a
// breadcrumb when the extension comes up.

chrome.runtime.onInstalled.addListener((details) => {
  console.info('[SentinelQA] installed', details.reason);
});
