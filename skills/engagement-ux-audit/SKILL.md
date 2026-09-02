---
name: engagement-ux-audit
description: >
  Production-grade auditor for on-site referral engagement and landing UX.
  Detects missing heading anchor IDs (#section-id) for AI deep-link citations,
  weak above-the-fold value clarity (3-second orientation rule), missing CTAs,
  intrusive blocking modals and paywalls, high cognitive load, and unscannable text walls.
license: Apache-2.0
allowed-tools: [run_command, view_file]
---

# Engagement UX Audit (On-Site Referral Engagement & Retention)

## When to use
Use this skill when diagnosing why visitors referred from AI assistant citations (ChatGPT, Perplexity, Claude, Gemini, SearchGPT) immediately bounce upon arrival, or when optimizing a website to convert AI-driven referral traffic.

## Inputs
- `target_url` (string): Absolute URL of the website to audit (e.g. `https://example.com`).
- `site_context` (dict, optional): Pre-fetched in-memory payload provided by `audit-orchestrator`.
- `raw_html` (string, optional): Direct raw HTML string for unit test evaluation.

## Procedure
1. **Audit Heading Anchor IDs & Deep-Link Jumpability (Subskill 5.1)**:
   - Run `scripts/heading_anchor_auditor.py` to extract all `<h2>` and `<h3>` section headings.
   - Verify presence of HTML `id` attributes enabling `#fragment` jumps.
   - Detect duplicate `id` values and generic non-descriptive slugs (`id="section"`).
   - Flag excessive dead fragment links (`href="#"`).

2. **Audit Above-The-Fold Value Clarity (Subskill 5.2)**:
   - Run `scripts/viewport_clarity_checker.py` on the top 100 words and hero section.
   - Evaluate primary headline for a descriptive entity value proposition (the 3-second orientation rule).
   - Check for a visible, accessible Call-To-Action (CTA button/link).

3. **Audit Intrusive Interstitial Friction & Paywalls (Subskill 5.3)**:
   - Run `scripts/interstitial_friction_detector.py` to detect full-screen modal overlays, newsletter paywalls, and blocking dialogs triggered on load.
   - Flag gating mechanisms that obstruct the visitor from reading the cited answer.

4. **Audit Cognitive Load & Scannability Formatting (Subskill 5.4)**:
   - Run `scripts/readability_cognitive_scorer.py` on clean body prose.
   - Calculate Flesch Reading Ease score and average sentence length.
   - Audit scannability features on long content: bulleted lists (`<ul>`, `<ol>`), bold highlights (`<strong>`), and paragraph lengths.

5. **Synthesize Findings**:
   - Aggregate all findings through `scripts/run_engagement_audit.py` into a unified list matching `report_schema.json`.

## Output
Returns a structured JSON array of findings adhering to `report_schema.json`. Each finding contains:
- `id`: Canonical rule identifier (e.g. `F-ENG-001`).
- `skill_id`: `"engagement-ux-audit"`.
- `title`: Concise summary of the defect.
- `severity`: `"critical"`, `"high"`, `"medium"`, or `"low"`.
- `impact_area`: `"on_site_engagement"`.
- `evidence`: Empirical proof (heading counts, Flesch scores, modal class names).
- `suggested_action`: Actionable remediation with `summary`, `priority`, `rationale`, and copy-pasteable `code_fix_example`.

## Failure Modes & Rule IDs Catalog

| Rule ID | Severity | Failure Mode Title | Subskill Engine | Detection Trigger |
| :---: | :---: | :--- | :--- | :--- |
| **`F-ENG-001`** | `High` | Missing Heading Anchor IDs for Deep Citations | Subskill 5.1 (`heading_anchor_auditor.py`) | $> 35\%$ of `<h2>`/`<h3>` headings lack `id` attributes on multi-section pages. |
| **`F-ENG-002`** | `Medium` | Duplicate or Non-Descriptive Anchor IDs | Subskill 5.1 (`heading_anchor_auditor.py`) | Headings share duplicate IDs or use generic identifiers (`id="section"`). |
| **`F-ENG-003`** | `High` | Weak Above-The-Fold Value Clarity (3s Rule) | Subskill 5.2 (`viewport_clarity_checker.py`) | Primary hero heading lacks substance or consists of an abstract slogan. |
| **`F-ENG-004`** | `Medium` | Missing Visible Above-The-Fold CTA | Subskill 5.2 (`viewport_clarity_checker.py`) | Top viewport contains 0 actionable Call-To-Action buttons or links. |
| **`F-ENG-005`** | `High` | Intrusive Blocking Modal or Interstitial | Subskill 5.3 (`interstitial_friction_detector.py`) | Full-screen overlay, newsletter popup, or blocking script triggers on load. |
| **`F-ENG-006`** | `Medium` | High Cognitive Load / Low Readability | Subskill 5.4 (`readability_cognitive_scorer.py`) | Flesch score $< 35$ or ($< 45$ with avg sentence length $> 24$ words). |
| **`F-ENG-007`** | `Low` | Dense Wall-Of-Text Lacking Scannability | Subskill 5.4 (`readability_cognitive_scorer.py`) | Content $> 400$ words lacks bulleted lists, bold highlights, or has giant paragraphs. |
| **`F-ENG-008`** | `Low` | Interactive Elements Use Dead Anchor Fragments | Subskill 5.1 (`heading_anchor_auditor.py`) | Detected $\ge 3$ anchor links relying on dummy `href="#"` or `href="#top"`. |

