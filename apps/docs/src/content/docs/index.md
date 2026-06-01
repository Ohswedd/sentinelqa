---
title: SentinelQA
description: Playwright-native release-confidence engine for LLM-built and human-built software.
template: splash
hero: tagline: Answer one question with evidence — can this software be trusted enough to ship? actions: - text: Install link: /get-started/install/ icon: right-arrow variant: primary - text: View on GitHub link: https://github.com/Ohswedd/sentinelqa icon: external variant: minimal
---

import { Card, CardGrid } from "@astrojs/starlight/components";

## What SentinelQA does

SentinelQA crawls your app, generates Playwright tests, runs them, and turns
the result into one number plus an explainable verdict: **release-decision**.

It is built for two audiences: human engineers who want a defensible
quality bar in CI, and AI coding agents that need an evidence-grounded
loop to ship features safely.

<CardGrid> <Card title="Discover" icon="magnifier"> HTTP + Playwright crawl. Map routes, forms, APIs, auth boundaries. </Card> <Card title="Plan + Generate" icon="setting"> Deterministic-first planner; Playwright spec generator with semantic locators. </Card> <Card title="Run + Analyze" icon="rocket"> Local + Docker runners. Failure categorization, root-cause hypothesis, retry/quarantine logic. </Card> <Card title="Score + Decide" icon="approve-check"> Reproducible 0–100 quality score with a policy-gated release decision. </Card>
</CardGrid>

## What SentinelQA is not

- It is **not** a stealth automation tool. We never bypass bot detection, CAPTCHAs, or rate limits.
- It is **not** a destructive scanner. Unsafe targets are blocked at config load.
- It is **not** a closed cloud product. The core engine is open source and runs entirely on your machine or CI.

See the [Safety boundary](/concepts/safety-boundary/) for the full list
of forbidden capabilities.
