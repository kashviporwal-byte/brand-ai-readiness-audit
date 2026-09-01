---
name: entity-semantics-audit
description: >
  Production-grade auditor for website entity semantics and AI knowledge graph readiness.
  Detects missing or malformed Schema.org JSON-LD structured data (Organization, Product, Service),
  absent or low-quality sameAs entity disambiguation links (Wikidata, Wikipedia, Crunchbase),
  lack of quotable definition sentences in top 200 visible words, and missing locale/audience
  grounding (hreflang, areaServed, inLanguage, geo-meta tags).
license: Apache-2.0
allowed-tools: [run_command, view_file]
---

# Entity Semantics Audit (AI Knowledge Graph & Entity Grounding)

## When to use
Use this skill when diagnosing why AI assistants:
1. Hallucinate or confuse a brand with a similarly-named competitor or entity.
2. Cite outdated or fabricated facts about a brand's products, founders, or pricing.
3. Cannot answer "What is [Brand]?" with an accurate, direct quote from the brand's own site.
4. Serve incorrect regional content or ignore locale-specific pages in AI-generated answers.

## Inputs
- `target_url` (string): The absolute URL of the web page to audit (e.g. `https://example.com`).
- `site_context` (dict, optional): The pre-parsed in-memory payload provided by `audit-orchestrator`.
- `raw_html` (string, optional): Direct raw HTML string for offline / unit-test evaluation.

## Procedure
1. **Audit Schema.org JSON-LD Structured Data (3.1)**:
   - Run `scripts/jsonld_schema_auditor.py` to extract all `<script type="application/ld+json">` blocks.
   - Attempt JSON parsing of each block; flag malformed blocks under `F-ENT-003`.
   - Flatten `@graph` wrappers; classify schemas by `@type` into core entity vs. content types.
   - Check for presence of core entity types (`Organization`, `Product`, `Service`, etc.) — emit `F-ENT-001` if absent.
   - Validate required field completeness (`name`, `description`, `url`, `logo`, `offers`) — emit `F-ENT-002` if gaps found.

2. **Audit Entity Disambiguation via sameAs (3.2)**:
   - Run `scripts/sameas_disambiguator.py` to extract `sameAs` arrays from all JSON-LD blocks.
   - Classify each link as Tier-1 KG (Wikidata/Wikipedia), Tier-2 directory (Crunchbase/SEC), or Tier-3 social (LinkedIn/GitHub).
   - Emit `F-ENT-004` if no `sameAs` links exist anywhere.
   - Emit `F-ENT-005` if `sameAs` exists but lacks Tier-1 KG anchors (Wikidata/Wikipedia).

3. **Audit Quotable Definition Sentences (3.3)**:
   - Run `scripts/quotable_definition_checker.py` to extract visible text skipping nav/footer/scripts.
   - Scan first 200 visible words and meta description for `"[X] is a/an [type] that [provides...]"` patterns.
   - Score matched sentences for marketing jargon density using a 35-term lexicon.
   - Emit `F-ENT-006` if no definition pattern found; emit `F-ENT-007` if found but jargon-heavy.

4. **Audit Locale & Audience Grounding (3.4)**:
   - Run `scripts/locale_audience_auditor.py` to parse hreflang tags, geo-meta tags, and JSON-LD locale fields.
   - Detect multi-language signals (`inLanguage`, multiple hreflang entries).
   - Emit `F-ENT-008` if multi-language signals exist but hreflang tags are missing.
   - Emit `F-ENT-009` if no `areaServed`, `inLanguage`, `audience`, or geo-meta tags found.

5. **Compile & Return Output**:
   - Fan all findings from 4 subskills through `scripts/run_entity_audit.py` into a unified list.

## Output
Returns a structured JSON array of findings. Each finding strictly includes:
- `id`: Canonical rule code (e.g., `F-ENT-001`, `F-ENT-006`).
- `skill_id`: `"entity-semantics-audit"`.
- `title`: Precise defect summary.
- `severity`: Ranked as `"critical"`, `"high"`, `"medium"`, or `"low"`.
- `impact_area`: `"ai_discoverability"`.
- `evidence`: Quantitative proof (schema type counts, sameAs link inventory, word previews).
- `suggested_action`: Actionable remediation containing `summary`, `priority`, `rationale`, and copy-pasteable `code_fix_example`.

## Rule Reference

| Rule ID    | Severity | Subskill | Trigger Condition |
|------------|----------|----------|-------------------|
| F-ENT-001  | high     | 3.1      | No Organization / Product JSON-LD schema found |
| F-ENT-002  | medium   | 3.1      | Schema present but missing critical fields (description, logo, offers) |
| F-ENT-003  | high     | 3.1      | JSON-LD block fails JSON.parse() — silently discarded by all crawlers |
| F-ENT-004  | high     | 3.2      | No sameAs links in JSON-LD; no authority outbound links on page |
| F-ENT-005  | medium   | 3.2      | sameAs present but lacks Tier-1 KG anchors (Wikidata / Wikipedia) |
| F-ENT-006  | high     | 3.3      | No quotable definition sentence in top 200 words or meta description |
| F-ENT-007  | medium   | 3.3      | Definition sentence found but ≥3 marketing jargon / buzzword terms |
| F-ENT-008  | medium   | 3.4      | Multi-language signals detected but hreflang alternate tags absent |
| F-ENT-009  | low      | 3.4      | No areaServed / inLanguage / audience schema or geo-meta tags found |
