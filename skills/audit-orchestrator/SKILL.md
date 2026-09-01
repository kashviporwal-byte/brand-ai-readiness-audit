---
name: audit-orchestrator
description: Master orchestrator for Brand AI-Readiness Audit. Coordinates single-pass polite crawling, fans out in-memory payloads to specialized domain skills, deterministically scores severity, and emits the final audit report.
license: Apache-2.0
allowed-tools: [run_command, view_file]
---

# Audit Orchestrator

## When to use
Use when an autonomous agent is tasked with auditing any website for AI discoverability and on-site engagement readiness.

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
