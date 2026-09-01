"""
Subskill 2.1: Client-Side JS Hydration & SPA Disparity Auditor (Hardened)
Audits raw HTML payloads against expected text density to identify
Single Page Application hydration traps where content is invisible to raw HTTP fetchers.
"""

import re
from html.parser import HTMLParser


class RawTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ignored_depth = 0
        self.ignored_tags = {"script", "style", "svg", "noscript", "template", "head"}
        self.text_chunks = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.ignored_tags:
            self.ignored_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in self.ignored_tags and self.ignored_depth > 0:
            self.ignored_depth -= 1

    def handle_data(self, data):
        if self.ignored_depth == 0:
            clean = data.strip()
            if clean:
                self.text_chunks.append(clean)

    def get_text(self):
        return " ".join(self.text_chunks)


def clean_raw_html_fallback(raw_html):
    """
    Forensic Fallback: Safely strips script, style, and template tags
    BEFORE stripping remaining HTML tags so minified JS is NEVER counted as visible text.
    """
    cleaned = raw_html
    for tag in ["script", "style", "template", "svg", "noscript", "head"]:
        cleaned = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", " ", cleaned, flags=re.DOTALL | re.IGNORECASE)
    no_tags = re.sub(r"<[^>]+>", " ", cleaned)
    return re.sub(r"\s+", " ", no_tags).strip()


def is_spa_mount_element(raw_html):
    """
    Checks whether the HTML contains a standard SPA root mount element.
    Uses token matching splitting on hyphens, underscores, and camelCase boundaries
    to support ids like 'appRoot', 'mainApp', 'reactAppContainer', and 'AppShell'
    while preventing substring false positives on 'main-content', 'maintenance-banner', 'reviews', etc.
    """
    matches = re.finditer(r'<(?:div|section|main)\s+[^>]*id=["\']([^"\']+)["\'][^>]*>\s*</(?:div|section|main)>', raw_html, re.IGNORECASE)
    for m in matches:
        raw_id = m.group(1).strip()
        raw_tokens = re.split(r'[-_]|(?<=[a-z0-9])(?=[A-Z])', raw_id)
        tokens = {t.lower() for t in raw_tokens if t}
        if tokens & {'app', 'root', 'mount', 'application', 'outlet'}:
            return True
        elem_lower = raw_id.lower()
        if elem_lower.startswith(('ember', 'svelte', 'qwik')):
            return True
    return False


def check_hydration_gap(raw_html, page_url=""):
    """
    Evaluates the raw HTML to detect whether critical content is locked
    behind client-side JavaScript hydration.
    """
    findings = []
    if not raw_html or len(raw_html.strip()) == 0:
        return findings

    # 1. Extract raw visible text safely
    parser = RawTextExtractor()
    try:
        parser.feed(raw_html)
        visible_text = parser.get_text()
    except Exception:
        visible_text = clean_raw_html_fallback(raw_html)

    # Double check fallback if parser yielded empty on large markup
    if len(visible_text) == 0 and len(raw_html) > 1000:
        visible_text = clean_raw_html_fallback(raw_html)

    word_count = len(visible_text.split())
    raw_size_bytes = len(raw_html.encode("utf-8"))

    # 2. Modern Framework Footprint Detection (Next.js App router, Pages router, Nuxt 3, Astro, Remix, Vite)
    spa_framework_patterns = [
        (r'<div\s+id=["\']root["\']\s*>\s*</div>', 'React Client SPA (<div id="root">)'),
        (r'<div\s+id=["\']__next["\']\s*>\s*</div>', 'Next.js Pages Router client mount (<div id="__next">)'),
        (r'self\.__next_f\.push', 'Next.js App Router streaming hydration chunk (self.__next_f)'),
        (r'<div\s+id=["\']app["\']\s*>\s*</div>', 'Vue/Vite SPA client mount (<div id="app">)'),
        (r'<app-root\s*>\s*</app-root>', 'Angular application root (<app-root>)'),
        (r'window\.__INITIAL_STATE__', 'Client hydration state script without static pre-rendering'),
        (r'window\.__remixContext', 'Remix application context hydration bundle'),
        (r'<astro-island\b', 'Astro partial hydration island'),
        (r'window\.__NUXT__', 'Nuxt.js client hydration payload')
    ]

    detected_spa_signatures = []
    for pattern, name in spa_framework_patterns:
        if re.search(pattern, raw_html, re.IGNORECASE):
            detected_spa_signatures.append(name)

    # 3. Check for noscript fallback
    noscript_match = re.search(r"<noscript[^>]*>(.*?)</noscript>", raw_html, re.IGNORECASE | re.DOTALL)
    noscript_quality = "none"
    if noscript_match:
        noscript_content = noscript_match.group(1).strip()
        if re.search(r"enable\s+javascript|turn\s+on\s+javascript|browser\s+does\s+not\s+support", noscript_content, re.IGNORECASE):
            noscript_quality = "generic_warning"
        elif len(noscript_content.split()) > 20:
            noscript_quality = "substantive"
        else:
            noscript_quality = "minimal"

    # 4. Precise Generic Client Shell Detection (Token-anchored mount div + external script)
    has_script_src = bool(re.search(r'<script[^>]+src=["\'][^"\']+["\']', raw_html, re.IGNORECASE))
    has_spa_mount = is_spa_mount_element(raw_html)
    is_generic_client_shell = (word_count < 40 and has_script_src and has_spa_mount)
    is_js_dependent = bool(detected_spa_signatures or is_generic_client_shell or (has_script_src and has_spa_mount))

    # 5. Evaluate Findings
    # Case A: Proven Client-Side JS Hydration Trap (< 60 words + confirmed JS shell/mount)
    if is_js_dependent and word_count < 60:
        framework_label = ', '.join(detected_spa_signatures[:2]) if detected_spa_signatures else "Client JavaScript Application Shell"
        findings.append({
            "id": "F-REND-001",
            "skill_id": "render-extraction-audit",
            "title": "Client-side JS hydration trap detected (empty SPA body shell)",
            "severity": "critical",
            "impact_area": "ai_discoverability",
            "evidence": f"Target page contains only {word_count} extractable words in raw HTML (Payload: {raw_size_bytes:,} bytes). Detected architecture: {framework_label}. Noscript fallback status: {noscript_quality}.",
            "suggested_action": {
                "summary": "Implement Server-Side Rendering (SSR) or Static Site Generation (SSG) so raw HTML contains full text content.",
                "priority": "critical",
                "rationale": "AI crawlers like GPTBot and search indexing engines frequently fetch raw HTML without executing client-side JavaScript bundles. An empty body shell renders the brand completely invisible to AI assistants.",
                "code_fix_example": "// Next.js: Ensure server components are default (avoid 'use client' on root layout)\n// Pages router: export async function getStaticProps() { return { props: { data } }; }"
            }
        })
    elif word_count < 15:
        # Case B: Static Thin Content (< 15 words) with NO client-side JS dependency
        findings.append({
            "id": "F-REND-013",
            "skill_id": "render-extraction-audit",
            "title": "Extremely sparse static document payload lacks substantive brand facts",
            "severity": "low",
            "impact_area": "ai_discoverability",
            "evidence": f"Document contains only {word_count} extractable words and zero client-side hydration mounts. Static payload is too thin for AI retrieval engines to answer questions about the brand.",
            "suggested_action": {
                "summary": "Expand static page copy to include substantive brand overview and value proposition.",
                "priority": "low",
                "rationale": "LLMs and search indexing crawlers require sufficient descriptive text to understand the entity's offering.",
                "code_fix_example": "<main>\n  <h1>Acme Inc</h1>\n  <p>Acme delivers automated enterprise workflow orchestration with real-time event routing...</p>\n</main>"
            }
        })
    elif word_count < 100 and raw_size_bytes > 30000:
        # Case C: Heavy markup/script payload (> 30KB) but extremely sparse extractable text
        findings.append({
            "id": "F-REND-001",
            "skill_id": "render-extraction-audit",
            "title": "Abnormally low raw text density indicates client-side rendering dependency",
            "severity": "high",
            "impact_area": "ai_discoverability",
            "evidence": f"Raw HTML size is {raw_size_bytes:,} bytes, but contains only {word_count} extractable words. High code-to-content disparity indicates content is loaded dynamically via JavaScript.",
            "suggested_action": {
                "summary": "Pre-render core page text into the initial HTML document payload.",
                "priority": "high",
                "rationale": "Search crawlers and AI answer retrieval engines prioritize documents with high initial information density.",
                "code_fix_example": "<main>\n  <h1>Platform Overview</h1>\n  <p>Static pre-rendered summary visible immediately to raw HTTP GET fetchers.</p>\n</main>"
            }
        })

    # Noscript warning finding
    if detected_spa_signatures and noscript_quality in ("none", "generic_warning"):
        findings.append({
            "id": "F-REND-002",
            "skill_id": "render-extraction-audit",
            "title": "Missing substantive <noscript> fallback summary for non-JS scrapers",
            "severity": "medium",
            "impact_area": "ai_discoverability",
            "evidence": f"Client-side rendered page provides '{noscript_quality}' noscript fallback. Scrapers bypassing JS receive no informative fallback summary.",
            "suggested_action": {
                "summary": "Provide an accessible <noscript> section containing a factual 200-word overview of the page.",
                "priority": "medium",
                "rationale": "Ensures baseline text extraction succeeds even when headless execution fails or times out.",
                "code_fix_example": '<noscript>\n  <div class="no-js-summary">\n    <h2>Acme Cloud Platform</h2>\n    <p>Acme delivers automated enterprise workflow orchestration with sub-millisecond event streaming...</p>\n  </div>\n</noscript>'
            }
        })

    return findings
