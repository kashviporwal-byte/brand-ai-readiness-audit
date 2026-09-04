---
name: crawl-bot-access
description: Audits website accessibility for AI search crawlers (GPTBot, ClaudeBot, PerplexityBot), robots.txt directives, X-Robots-Tag HTTP headers, sitemaps, and llms.txt adoption.
license: Apache-2.0
allowed-tools: [run_command, view_file]
---

# Crawl & Bot Access Audit

## When to use
Use when diagnosing why an AI search engine (Perplexity, ChatGPT, Claude, Gemini) cannot reach, crawl, or index pages on a target website.

## Inputs
- `target_url` (string): Absolute URL of the website to audit (e.g. `https://example.com`).
- `site_context` (dict, optional): Pre-fetched in-memory payload provided by `audit-orchestrator`.

## Procedure
1. Inspect input and verify target URL accessibility.
2. Execute deterministic domain checks located in `scripts/`:
   - `robots_txt_checker.py`: Audits user-agent disallow blocks (`F-CRAWL-001`, `F-CRAWL-002`, `F-CRAWL-003`, `F-CRAWL-006`, `F-CRAWL-008`).
   - `http_header_auditor.py`: Audits `X-Robots-Tag` and `<meta name="robots">` (`F-CRAWL-004`, `F-CRAWL-005`).
   - `sitemap_auditor.py`: Audits sitemap reachability, lastmod freshness, and broken links (`F-CRAWL-007`, `F-CRAWL-009`, `F-CRAWL-010`).
   - `llms_txt_checker.py`: Audits `/llms.txt` and `/llms-full.txt` presence and markdown syntax (`F-CRAWL-011`, `F-CRAWL-012`).
3. Consult rules and heuristics located in `references/ai_crawler_manifests.md`.
4. Return findings adhering strictly to the contest report schema.

## Output
A JSON array of findings adhering to the unified schema:
- `id`: Canonical rule identifier (`F-CRAWL-001` through `F-CRAWL-012`).
- `skill_id`: `crawl-bot-access`.
- `title`: Concise defect headline.
- `severity`: One of `critical`, `high`, `medium`, `low`.
- `impact_area`: `crawl_accessibility`.
- `evidence`: Empirical proof (HTTP status, robots.txt directive, headers).
- `suggested_action`: Actionable remediation with `summary`, `priority`, `rationale`, and `code_fix_example`.

## Failure Modes Catalog

| Rule ID | Severity | Description |
| :--- | :---: | :--- |
| `F-CRAWL-001` | Critical | Global crawl block in robots.txt (`User-agent: * Disallow: /`) |
| `F-CRAWL-002` | Critical | Tier-1 AI crawler blocked (`GPTBot`, `ClaudeBot`, `PerplexityBot`) |
| `F-CRAWL-003` | Medium | Tier-2 AI crawler blocked (`Google-Extended`, `Amazonbot`, `Bytespider`) |
| `F-CRAWL-004` | Critical | AI/Index blocked via HTTP `X-Robots-Tag` (`noai`, `noindex`, `noimageai`) |
| `F-CRAWL-005` | High | AI snippet generation blocked via `nosnippet` |
| `F-CRAWL-006` | Medium | `robots.txt` file missing (HTTP 404) |
| `F-CRAWL-007` | High | `sitemap.xml` unreachable or empty |
| `F-CRAWL-008` | Medium | Sitemap URL is omitted from `robots.txt` |
| `F-CRAWL-009` | Medium | Stale or missing `<lastmod>` timestamps in sitemap |
| `F-CRAWL-010` | High | Broken URLs (HTTP 4xx/5xx) found in sitemap |
| `F-CRAWL-011` | Low | Missing or malformed `/llms.txt` AI discovery manifest |
| `F-CRAWL-012` | Low | Missing or malformed `/llms-full.txt` full-content manifest |
| `F-CRAWL-013` | Medium | Audited primary URL explicitly disallowed by `robots.txt` for AI crawlers |
| `F-CRAWL-014` | Medium | Excessive `Crawl-delay:` directive (>10s) in `robots.txt` |

