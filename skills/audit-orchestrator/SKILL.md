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

## Procedure & Execution Instructions for AI Agent

The AI Agent should invoke the Python orchestrator using its command execution tool (`run_command` / bash). Choose the appropriate mode based on the user's intent:

### Mode 1: Standard Single-Page Audit (Default)
Use this default mode when auditing a specific landing page, documentation page, or target URL:
```bash
python skills/audit-orchestrator/scripts/orchestrate_audit.py <target_url> --output report.json
```

### Mode 2: Multi-Page Site-Wide Audit (Sitemap Traversal)
Use this mode when instructed to evaluate multiple pages across the website architecture:
```bash
python skills/audit-orchestrator/scripts/orchestrate_audit.py <target_url> --multi-page --max-pages 3 --output report.json
```
This automatically inspects `robots.txt` and `sitemap.xml`, discovers high-intent secondary pages (e.g. `/pricing`, `/docs`, `/about`), and audits them concurrently alongside the homepage.

## Internal Architecture & Composition
The orchestrator executes a clean 4-stage pipeline:
1. **Polite Crawler:** Fetches HTML, evaluates HTTP status, response headers, and sitemaps.
2. **Concurrent Skill Dispatch:** Fans out in-memory `SiteContext` across all 5 registered domain skills in parallel:
   - `crawl-bot-access`: AI crawler directives, robots.txt, sitemaps, llms.txt.
   - `render-extraction-audit`: JS hydration traps, missing image alt, canvas/media, heading hierarchy.
   - `entity-semantics-audit`: Schema.org JSON-LD, sameAs disambiguation, quotable definitions.
   - `freshness-corroboration`: Temporal freshness, cross-web corroboration, information density.
   - `engagement-ux-audit`: Heading anchor IDs, 3-second value proposition, popups, cognitive load.
3. **Deduplication & Deterministic Scoring:** Deduplicates findings, computes the AI Readiness Score (0-100), and prioritizes top recommendations.
4. **Structured Report Emission:** Outputs terminal summary and writes strictly compliant `report.json`.

## Output Specification
Emits a structured JSON report adhering strictly to `report_schema.json`:
- `site` (string): Audited base URL.
- `audited_at` (string, ISO 8601 UTC): Audit timestamp.
- `pages_audited` (array of strings): List of all crawled URLs.
- `total_pages` (integer): Total count of pages audited.
- `summary` (object): Tally of `total_findings`, `critical`, `high`, `medium`, `low`.
- `findings` (array of objects):
  - `id`: Canonical rule identifier (e.g. `F-REND-001`).
  - `page_url`: Source URL where the finding was detected.
  - `title`: Concise summary of the defect.
  - `severity`: One of `critical`, `high`, `medium`, `low`.
  - `evidence`: Empirical proof (HTTP status, DOM element count, missing attribute).
  - `suggested_action`: Actionable remediation with `summary`, `priority`, `rationale`, and `code_fix_example`.
- `proactive_recommendations` (array of objects): Top beyond-defect recommendations for AI referral conversion.
