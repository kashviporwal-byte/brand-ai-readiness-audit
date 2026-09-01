# Machine Readability & Extraction Failure Modes

This document details the engineering failure modes that prevent modern AI assistants (ChatGPT, Claude, Perplexity, Gemini, SearchGPT) and search crawlers from successfully extracting knowledge from web pages.

---

## 1. Client-Side Hydration Dependency (The SPA Trap)

### Mechanism of Failure
Modern web applications often rely on client-side JavaScript frameworks (React, Vue, Angular, Svelte) where the web server responds with an empty HTML body containing a root mounting element and bundle script references:
```html
<!DOCTYPE html>
<html>
  <head><title>Modern App</title></head>
  <body>
    <div id="root"></div>
    <script src="/static/js/bundle.182fa.js"></script>
  </body>
</html>
```

### Why AI Crawlers Fail
1. **Compute Constraints & Budgeting**: Crawlers such as `GPTBot`, `ClaudeBot`, and standard HTTP fetchers prioritize speed and cost. Running a headless Chromium browser with a JavaScript V8 execution engine costs 10x-50x more compute than a simple raw HTTP `GET` request.
2. **Hydration Timing**: Many crawlers execute with aggressive timeout thresholds (2 to 4 seconds). Even if a headless browser is used, network requests for client bundles or asynchronous API fetches that resolve after the initial load event are truncated.
3. **The Result**: The crawler extracts 0 to 20 words of text, concluding the page has zero substantive information.

---

## 2. Non-Text Locked Facts (Multimodal Extraction Barriers)

### Mechanism of Failure
Valuable facts (e.g., pricing tiers, platform architecture, customer metrics, benchmark results) are frequently embedded directly into raster images (PNG, JPEG, WebP) without text equivalents:
```html
<div class="pricing-card">
  <img src="/assets/tier-matrix.png" />
</div>
```

### Why AI Crawlers Fail
1. **Text Extractors Miss Images Entirely**: Plain text extractors (used in majority of RAG pipelines) bypass `<img>` tags completely unless an `alt` attribute is present.
2. **OCR Limitations**: Even multimodal models (GPT-4o, Claude 3.5 Sonnet) struggle with low-resolution raster text, unusual typography, or compressed artifacts.
3. **Generic Alt Placeholders**: Using `alt="image.png"`, `alt="graphic"`, or `alt="screenshot"` acts as a decoy that tells the AI nothing about the underlying facts.

---

## 3. Rich Media & Interactive Element Traps

### Canvas & WebGL Visualizations
Elements rendered onto `<canvas>` tags exist solely as memory bitmaps in the browser's GPU/canvas buffer. The DOM contains zero text nodes. Unless accompanied by `aria-label`, `aria-describedby`, or fallback text inside `<canvas>Fallback</canvas>`, the data is invisible.

### Video & Audio Content Without Transcripts
Audio and video content cannot be ingested by text crawlers. Without explicit `<track kind="captions" src="...">` WebVTT tracks or textual transcript elements, key product demonstrations and interviews cannot be cited.

---

## 4. Semantic Hierarchy & Outline Breakdown

### Why Heading Outlines Matter to AI
AI retrieval systems chunk long web pages into vector embeddings based on heading sections (`<h1>`, `<h2>`, `<h3>`).
- **Level Skipping**: An `<h1>` followed immediately by an `<h4>` breaks the hierarchical parent-child relationship in vector chunkers.
- **Multiple H1s**: Creates ambiguity regarding the primary entity and topic of the page.
- **Div Soup**: Pages lacking `<main>` and `<article>` force the AI extractor to process navigation links, footer disclaimers, and sidebar ads with equal weight as the main body.

---

## 5. Master Failure Modes & Rules Catalog (`F-REND-001` to `F-REND-013`)

The following table provides the canonical specification for all 13 detectable defect rules enforced by `render-extraction-audit`:

| Rule ID | Severity | Failure Mode Title | Subskill Engine | Detection Trigger | Remediation Strategy |
| :---: | :---: | :--- | :--- | :--- | :--- |
| **`F-REND-001`** | `Critical` / `High` | Client-Side JS Hydration Trap | Subskill 2.1 (`dom_hydrator_diff.py`) | Raw HTML word count $< 60$ with detected SPA framework mount or generic client shell. | Implement Server-Side Rendering (SSR) or Static Site Generation (SSG). |
| **`F-REND-002`** | `Medium` | Missing Substantive `<noscript>` Fallback | Subskill 2.1 (`dom_hydrator_diff.py`) | Client-rendered page provides missing or generic "please enable JS" noscript warning. | Add a 200-word factual markdown/HTML summary inside `<noscript>`. |
| **`F-REND-003`** | `High` / `Medium` | Trapped Facts in Images | Subskill 2.2 (`non_text_auditor.py`) | Informational images missing `alt`, using placeholder (`image.png`), or raw filenames. | Provide descriptive, factual alt text conveying underlying data and workflows. |
| **`F-REND-004`** | `Medium` | Canvas/WebGL Without Fallback | Subskill 2.3 (`non_text_auditor.py`) | `<canvas>` elements lacking `aria-label`, `aria-describedby`, or fallback DOM text. | Add `aria-label` or adjacent accessible data table. |
| **`F-REND-005`** | `Medium` | Video/Audio Without Transcripts | Subskill 2.3 (`non_text_auditor.py`) | `<video>` or `<audio>` lacking `<track kind="captions">` or adjacent transcript container. | Provide WebVTT captions and an expandable transcript section. |
| **`F-REND-006`** | `High` / `Medium` | Missing or Competing `<h1>` Headings | Subskill 2.4 (`semantic_html_checker.py`) | Document has 0 visible `<h1>` tags or $> 1$ competing `<h1>` tags. | Include exactly one descriptive `<h1>` representing the primary page entity. |
| **`F-REND-007`** | `Medium` | Skipped Heading Outline Levels | Subskill 2.4 (`semantic_html_checker.py`) | Heading outline jumps levels (e.g. `<h1>` directly to `<h3>` or `<h4>`). | Follow a strict sequential hierarchy (H1 $\rightarrow$ H2 $\rightarrow$ H3). |
| **`F-REND-008`** | `Low` | Empty Heading Elements | Subskill 2.4 (`semantic_html_checker.py`) | Heading tags (`<h1>`-`<h6>`) containing zero text nodes (used for CSS spacing). | Remove empty tags or populate with descriptive section headers. |
| **`F-REND-009`** | `Medium` | Div Soup / Missing Semantic Landmarks | Subskill 2.4 (`semantic_html_checker.py`) | Document contains 0 `<main>` and 0 `<article>` landmarks. | Wrap core textual content in a semantic `<main>` landmark container. |
| **`F-REND-010`** | `Low` | Excessive Code-to-Text Bloat | Subskill 2.4 (`semantic_html_checker.py`) | Text-to-HTML density $< 5\%$ on payloads $> 40\text{KB}$. | Externalize inline styles and tracking scripts to preserve LLM context windows. |
| **`F-REND-011`** | `Medium` | Complex SVG Data Charts Without Text | Subskill 2.3 (`non_text_auditor.py`) | Non-icon inline `<svg>` with $\ge 5$ data nodes lacking `<title>` or `<desc>`. | Include `<title>` and `<desc>` tags describing the chart's underlying metrics. |
| **`F-REND-012`** | `High` | Primary `<h1>` Heading Cloaked | Subskill 2.4 (`semantic_html_checker.py`) | `<h1>` heading hidden via `display:none`, `visibility:hidden`, or `aria-hidden="true"`. | Visually render the primary `<h1>` above the fold without CSS cloaking. |
| **`F-REND-013`** | `Low` | Sparse Static Document Payload | Subskill 2.1 (`dom_hydrator_diff.py`) | Raw HTML contains $< 15$ words and zero client-side JavaScript mounts. | Expand static page copy with substantive brand overview and value proposition. |
