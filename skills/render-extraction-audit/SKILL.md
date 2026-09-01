---
name: render-extraction-audit
description: Production-grade auditor for website machine readability and content extraction. Detects Single Page Application (SPA) client-side JS hydration traps where raw HTML is an empty shell, facts locked in non-text media (missing, placeholder, or filename alt text on images, canvas elements without aria-labels, videos lacking WebVTT transcripts), and broken semantic DOM outlines (missing/multiple H1s, level-skip heading anomalies, absence of main/article landmarks).
license: Apache-2.0
allowed-tools: [run_command, view_file]
---

# Render Extraction Audit (Machine Readability & Trapped Facts)

## When to use
Use this skill when diagnosing why AI assistants (ChatGPT, Claude, Perplexity, SearchGPT) or automated web crawlers:
1. See an empty or content-starved page due to client-side JavaScript hydration dependencies.
2. Miss critical data tables, architectures, or benchmark statistics trapped inside raster images or canvas graphics without text descriptions.
3. Fail to chunk and cite documentation cleanly due to broken heading hierarchies and generic `<div>` soup.

## Inputs
- `target_url` (string): The absolute URL of the web page to audit.
- `site_context` (dict, optional): The pre-parsed in-memory payload provided by `audit-orchestrator`.
- `raw_html` (string): Direct raw HTML string for offline evaluation.

## Procedure
1. **Analyze Client-Side Hydration Disparity**:
    - Run `scripts/dom_hydrator_diff.py` to extract raw visible body text.
    - Detect SPA mounting roots using token-anchored boundary matching (`<div id="root">`, `<div id="__next">`, `<div id="app">`, etc.).
    - Distinguish client-side JavaScript hydration traps (`F-REND-001`) from static thin content (`F-REND-013`).
    - Flag pages where raw text is `< 60` words while bundle scripts exceed `30KB`.
    - Audit `<noscript>` fallback quality.
2. **Audit Non-Text Trapped Facts**:
   - Run `scripts/non_text_auditor.py` to parse all `<img>`, `<canvas>`, `<video>`, and `<audio>` elements.
   - Discriminate decorative images (`role="presentation"`, `aria-hidden="true"`, `<figcaption>` context) to eliminate false positives.
   - Flag informational images with missing `alt`, generic placeholders (`alt="image"`), or raw filenames.
   - Check `<canvas>` for `aria-label` or fallback DOM text.
   - Audit complex inline `<svg>` data charts (>= 5 nodes) for `<title>` and `<desc>` accessible tags (`F-REND-011`).
   - Verify `<video>` elements contain `<track kind="captions">` with reachable `.vtt` tracks.
3. **Verify Semantic Hierarchy & Outline**:
   - Run `scripts/semantic_html_checker.py` to construct the document heading tree.
   - Extract logo image `alt` attributes when logos are nested in `<h1>` (preventing false positive empty headings).
   - Detect CSS-hidden headings (`display:none`, `aria-hidden="true"`) under `F-REND-012`.
   - Verify `<h1>` uniqueness (exactly one primary H1).
   - Detect heading level skips (e.g. `<h1>` jumping directly to `<h3>` or `<h4>`).
   - Audit semantic landmark containers (`<main>`, `<article>`) vs generic `<div>` wrappers.
   - Evaluate text-to-HTML density ratio (< 5% text-to-code triggers `F-REND-010`).
4. **Compile & Format Output**:
   - Invoke `scripts/run_render_audit.py` to aggregate all findings into the contest JSON schema.

## Output
Returns a structured JSON array of findings. Each finding strictly includes:
- `id`: Canonical rule code (e.g., `F-REND-001`, `F-REND-003`).
- `skill_id`: `"render-extraction-audit"`.
- `title`: Precise defect summary.
- `severity`: Ranked as `"critical"`, `"high"`, `"medium"`, or `"low"`.
- `impact_area`: `"ai_discoverability"`.
- `evidence`: Quantitative proof (word count, image ratios, heading sequence).
- `suggested_action`: Actionable remediation containing `summary`, `priority`, `rationale`, and copy-pasteable `code_fix_example`.

## Failure Modes & Rule IDs Catalog

| Rule ID | Severity | Failure Mode | Subskill Engine |
| :---: | :---: | :--- | :--- |
| **`F-REND-001`** | `Critical` / `High` | Client-Side JS Hydration Trap (Empty SPA Body Shell) | Subskill 2.1 (`dom_hydrator_diff.py`) |
| **`F-REND-002`** | `Medium` | Missing Substantive `<noscript>` Fallback | Subskill 2.1 (`dom_hydrator_diff.py`) |
| **`F-REND-003`** | `High` / `Medium` | Trapped Facts in Images (Missing/Placeholder/Filename Alt) | Subskill 2.2 (`non_text_auditor.py`) |
| **`F-REND-004`** | `Medium` | Interactive `<canvas>` Without Text Fallback | Subskill 2.3 (`non_text_auditor.py`) |
| **`F-REND-005`** | `Medium` | Video & Audio Content Without Transcripts/Captions | Subskill 2.3 (`non_text_auditor.py`) |
| **`F-REND-006`** | `High` / `Medium` | Missing or Competing `<h1>` Headings | Subskill 2.4 (`semantic_html_checker.py`) |
| **`F-REND-007`** | `Medium` | Broken Heading Hierarchy (Skipped Outline Levels) | Subskill 2.4 (`semantic_html_checker.py`) |
| **`F-REND-008`** | `Low` | Empty Heading Elements Used for CSS Spacing | Subskill 2.4 (`semantic_html_checker.py`) |
| **`F-REND-009`** | `Medium` | Div Soup (Absence of `<main>` / `<article>` Landmarks) | Subskill 2.4 (`semantic_html_checker.py`) |
| **`F-REND-010`** | `Low` | Excessive Code Bloat (Text Density $< 5\%$) | Subskill 2.4 (`semantic_html_checker.py`) |
| **`F-REND-011`** | `Medium` | Complex Inline SVG Data Charts Lacking `<title>`/`<desc>` | Subskill 2.3 (`non_text_auditor.py`) |
| **`F-REND-012`** | `High` | Primary `<h1>` Heading Hidden via CSS Cloaking | Subskill 2.4 (`semantic_html_checker.py`) |
| **`F-REND-013`** | `Low` | Sparse Static Document Payload ($< 15$ Words) | Subskill 2.1 (`dom_hydrator_diff.py`) |
