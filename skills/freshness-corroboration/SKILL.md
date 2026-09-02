---
name: freshness-corroboration
description: Production-grade auditor for website temporal freshness and AI summarization resilience. Detects missing or stale datePublished/dateModified metadata, copyright drift, multi-source factual claim conflicts (Appendix D 2-source consensus rule), and low information density pages that lose substance during AI extractive summarization (Appendix F).
license: Apache-2.0
allowed-tools: [run_command, view_file]
---

# Freshness Corroboration (Temporal Authority & Summarization Resilience)

## When to use
Use this skill when diagnosing why AI assistants (ChatGPT, Claude, Perplexity, SearchGPT) are:
1. Citing outdated facts, stale pricing, or deprecated product information from a website.
2. Generating hallucinated claims that contradict verifiable third-party source data.
3. Dropping or omitting core brand facts in AI email summaries, article digests, or synthesized answers due to low information density in the source content.

## Inputs
- `target_url` (string): The absolute URL of the web page to audit.
- `site_context` (dict, optional): The pre-parsed in-memory payload provided by `audit-orchestrator`.
- `raw_html` (string): Direct raw HTML string for offline or test evaluation.

## Procedure
1. **Audit Temporal Freshness & Copyright Timestamps**:
    - Run `scripts/temporal_freshness_checker.py` to extract all temporal signals.
    - Check JSON-LD `datePublished`, `dateModified`, and `uploadDate` within `<script type="application/ld+json">` blocks.
    - Parse `<meta>` tags: `article:published_time`, `article:modified_time`, `og:updated_time`, `DC.date`, `date`, `last-modified`.
    - Detect `<time datetime="...">` HTML elements in body content.
    - Validate all timestamps against ISO 8601 format and flag future-dated or corrupted values.
    - Detect copyright year strings in footer regions via regex (`© 2021`, `Copyright 2019-2022`, `(c) 2020`) and compare against the current calendar year.
    - Generates findings: `F-FRSH-001`, `F-FRSH-002`, `F-FRSH-003`.
2. **Audit Cross-Web Claim Corroboration (Appendix D)**:
    - Run `scripts/cross_web_corroborator.py` to extract core entity assertions from HTML and JSON-LD.
    - Extract entity claims: organization name, founding year, headquarters city/country, leadership/founders, and pricing tier labels.
    - Enforce the strict **2-source consensus rule**: A discrepancy against on-page claims is only escalated as a finding if at least 2 independent external authoritative sources corroborate the divergence. Single stale directory mismatches are suppressed as false positives.
    - Flag high-confidence multi-source factual conflicts that increase AI hallucination risk.
    - Generates findings: `F-FRSH-004`, `F-FRSH-005`.
3. **Audit Information Density & Summarization Resilience (Appendix F)**:
    - Run `scripts/information_density_evaluator.py` to parse visible body text content.
    - Strip navigation, header/footer boilerplate, scripts, and style blocks.
    - Classify tokens into substantive factual content vs marketing fluff/buzzwords.
    - Compute the Information Density Score: `(Substantive Tokens / Total Content Tokens) * 100`.
    - Simulate extractive AI summarization compression at 30% retention to detect fact drop-off.
    - Generates findings: `F-FRSH-006`, `F-FRSH-007`.
4. **Compile & Format Output**:
    - Invoke `scripts/run_freshness_audit.py` to aggregate all findings into the contest JSON schema.

## Output
Returns a structured JSON array of findings. Each finding strictly includes:
- `id`: Canonical rule code (e.g., `F-FRSH-001`, `F-FRSH-004`).
- `skill_id`: `"freshness-corroboration"`.
- `title`: Precise defect summary.
- `severity`: Ranked as `"critical"`, `"high"`, `"medium"`, or `"low"`.
- `impact_area`: `"ai_discoverability"`.
- `evidence`: Quantitative proof (extracted timestamp, copyright year delta, density score percentage, conflicting claim strings).
- `suggested_action`: Actionable remediation containing `summary`, `priority`, `rationale`, and copy-pasteable `code_fix_example`.

## Failure Modes & Rule IDs Catalog

| Rule ID | Severity | Failure Mode | Subskill Engine |
| :---: | :---: | :--- | :--- |
| **`F-FRSH-001`** | `High` | Missing `datePublished` / `dateModified` on Substantive Content Pages | Subskill 4.1 (`temporal_freshness_checker.py`) |
| **`F-FRSH-002`** | `Medium` | Stale Copyright Notice (>= 2 Years Out of Date) | Subskill 4.1 (`temporal_freshness_checker.py`) |
| **`F-FRSH-003`** | `Medium` | Malformed or Future-Dated ISO 8601 Temporal Timestamp | Subskill 4.1 (`temporal_freshness_checker.py`) |
| **`F-FRSH-004`** | `High` | Multi-Source Verified Factual Conflict (2-Source Consensus Rule Violated) | Subskill 4.2 (`cross_web_corroborator.py`) |
| **`F-FRSH-005`** | `Medium` | Uncorroborated Single-Source Claim with High Hallucination Risk | Subskill 4.2 (`cross_web_corroborator.py`) |
| **`F-FRSH-006`** | `High` / `Medium` | Low Information Density (< 30% / 30%–45% Substance-to-Noise Ratio) | Subskill 4.3 (`information_density_evaluator.py`) |
| **`F-FRSH-007`** | `Medium` | Excessive Buzzword Dilution Failing Appendix F Summarization Resilience | Subskill 4.3 (`information_density_evaluator.py`) |
