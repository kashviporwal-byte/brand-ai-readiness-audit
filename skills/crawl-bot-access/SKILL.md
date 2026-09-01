---
name: crawl-bot-access
description: Audits website accessibility for AI search crawlers, robots.txt directives for modern AI user-agents, X-Robots-Tag HTTP headers, sitemaps, and llms.txt adoption.
license: Apache-2.0
allowed-tools: [run_command, view_file]
---

# Crawl Bot Access

## When to use
Use when diagnosing why an AI assistant cannot reach, index, or discover pages on a target website.

## Inputs
- `target_url` (string): Absolute URL of the website to audit (e.g. `https://example.com`).
- `site_context` (dict, optional): Pre-fetched in-memory payload provided by `audit-orchestrator`.

## Procedure
1. Inspect input and verify target URL accessibility.
2. Execute deterministic domain checks located in `scripts/`.
3. Consult rules and heuristics located in `references/`.
4. Return findings adhering strictly to the contest report schema.

## Output
A JSON array of findings, each containing:
- `id`: Canonical rule identifier (e.g. `F-REND-001`).
- `title`: Concise summary of the defect.
- `severity`: One of `critical`, `high`, `medium`, `low`.
- `evidence`: Empirical proof (HTTP status, DOM element count, missing attribute).
- `suggested_action`: Actionable remediation with `summary`, `priority`, and code examples.
