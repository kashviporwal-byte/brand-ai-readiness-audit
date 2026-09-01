"""
Subskill 2.4: Semantic DOM & AI RAG Chunking Auditor (Hardened)
Audits heading hierarchy (H1 uniqueness, logo alt text recognition, level skips),
detects CSS-hidden heading cloaking, and evaluates text-to-code density.
"""

import re
from html.parser import HTMLParser


class SemanticHierarchyParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.headings = []
        self.landmarks = {
            "main": 0,
            "article": 0,
            "section": 0,
            "header": 0,
            "nav": 0,
            "footer": 0,
            "aside": 0
        }
        self.current_heading = None
        self.current_heading_text = []

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        attr_dict = {k.lower(): (v if v is not None else "") for k, v in attrs}

        if tag_lower in self.landmarks:
            self.landmarks[tag_lower] += 1

        if re.match(r"^h[1-6]$", tag_lower):
            style = attr_dict.get("style", "").lower()
            aria_hidden = attr_dict.get("aria-hidden", "").lower()
            css_class = attr_dict.get("class", "").lower()

            is_hidden = bool(
                re.search(r"display\s*:\s*none", style) or
                re.search(r"visibility\s*:\s*hidden", style) or
                aria_hidden == "true" or
                "sr-only" in css_class or
                "visually-hidden" in css_class
            )

            self.current_heading = {
                "tag": tag_lower,
                "level": int(tag_lower[1]),
                "id": attr_dict.get("id", None),
                "is_hidden": is_hidden
            }
            self.current_heading_text = []

        elif self.current_heading and tag_lower == "img":
            # BUG FIX: If heading contains an image logo, extract its alt or aria-label
            alt_text = attr_dict.get("alt", "").strip() or attr_dict.get("aria-label", "").strip()
            if alt_text:
                self.current_heading_text.append(alt_text)

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if re.match(r"^h[1-6]$", tag_lower) and self.current_heading:
            text = " ".join("".join(self.current_heading_text).split()).strip()
            self.current_heading["text"] = text
            self.headings.append(self.current_heading)
            self.current_heading = None

    def handle_data(self, data):
        if self.current_heading:
            self.current_heading_text.append(data)


def check_semantic_hierarchy(raw_html, page_url=""):
    """
    Validates heading outlines, semantic container landmarks, and text density.
    """
    findings = []
    if not raw_html:
        return findings

    parser = SemanticHierarchyParser()
    try:
        parser.feed(raw_html)
    except Exception:
        pass

    headings = parser.headings
    landmarks = parser.landmarks

    # 1. H1 Tag Validation
    h1_headings = [h for h in headings if h["level"] == 1]
    visible_h1s = [h for h in h1_headings if not h["is_hidden"]]
    hidden_h1s = [h for h in h1_headings if h["is_hidden"]]

    if len(visible_h1s) == 0:
        if len(hidden_h1s) > 0:
            findings.append({
                "id": "F-REND-012",
                "skill_id": "render-extraction-audit",
                "title": "Primary <h1> heading is hidden via CSS or aria-hidden",
                "severity": "high",
                "impact_area": "ai_discoverability",
                "evidence": f"Found {len(hidden_h1s)} <h1> heading(s) hidden via display:none, visibility:hidden, or aria-hidden='true'. Human and multimodal AI agents cannot perceive hidden headings.",
                "suggested_action": {
                    "summary": "Ensure the primary <h1> is visually rendered in the DOM above the fold.",
                    "priority": "high",
                    "rationale": "Search and AI agents penalize hidden heading cloaking to prevent manipulative keyword stuffing.",
                    "code_fix_example": "<h1>Acme Cloud Platform: Automated Workflow Orchestration</h1>"
                }
            })
        else:
            findings.append({
                "id": "F-REND-006",
                "skill_id": "render-extraction-audit",
                "title": "Missing primary <h1> heading tag",
                "severity": "high",
                "impact_area": "ai_discoverability",
                "evidence": "Document contains 0 <h1> heading tags. AI models rely on H1 to identify the core topic and entity of the page.",
                "suggested_action": {
                    "summary": "Introduce a single, descriptive <h1> tag encapsulating the primary entity and value proposition.",
                    "priority": "high",
                    "rationale": "Without an H1, AI document parsers struggle to establish the primary subject matter of the document, reducing citation confidence.",
                    "code_fix_example": "<h1>Acme Cloud Platform: Automated Enterprise Workflow Orchestration</h1>"
                }
            })
    elif len(visible_h1s) > 1:
        titles = [f"'{h['text'][:35]}...'" if len(h['text']) > 35 else f"'{h['text']}'" for h in visible_h1s]
        findings.append({
            "id": "F-REND-006",
            "skill_id": "render-extraction-audit",
            "title": "Multiple competing <h1> headings cause topical ambiguity",
            "severity": "medium",
            "impact_area": "ai_discoverability",
            "evidence": f"Found {len(visible_h1s)} separate <h1> tags ({', '.join(titles)}). A web document should maintain a single primary H1 landmark.",
            "suggested_action": {
                "summary": "Consolidate into a single primary <h1> tag and demote secondary titles to <h2>.",
                "priority": "medium",
                "rationale": "Multiple H1 tags dilute keyword authority and create ambiguity during vector embedding topic assignment.",
                "code_fix_example": "<!-- Change secondary H1 to H2 -->\n<h2>Secondary Section Title</h2>"
            }
        })

    # 2. Heading Level Sequence Skips (e.g. H1 -> H3 or H2 -> H5)
    level_skips = []
    if headings and headings[0]["level"] > 2:
        level_skips.append(f"Document root -> <{headings[0]['tag']}> ('{headings[0]['text'][:25]}')")

    for i in range(len(headings) - 1):
        curr_lvl = headings[i]["level"]
        next_lvl = headings[i + 1]["level"]
        if next_lvl > curr_lvl + 1:
            level_skips.append(f"<{headings[i]['tag']}> ('{headings[i]['text'][:25]}') -> <{headings[i+1]['tag']}> ('{headings[i+1]['text'][:25]}')")

    if level_skips:
        findings.append({
            "id": "F-REND-007",
            "skill_id": "render-extraction-audit",
            "title": "Broken heading hierarchy with skipped outline levels",
            "severity": "medium",
            "impact_area": "ai_discoverability",
            "evidence": f"Detected {len(level_skips)} instances where headings skip outline levels: {'; '.join(level_skips[:2])}.",
            "suggested_action": {
                "summary": "Restructure headings to follow a strict sequential hierarchy (H1 -> H2 -> H3) without skipping levels.",
                "priority": "medium",
                "rationale": "AI RAG pipelines build hierarchical chunk trees from headings. Skipping levels causes subtopics to be misattributed to incorrect parent topics.",
                "code_fix_example": "<h1>Platform</h1>\n<h2>Core Engine</h2>\n<h3>Sub-Process Ingestion</h3> <!-- Do not jump directly from H1 to H3 -->"
            }
        })

    # 3. Empty Headings
    empty_headings = [h for h in headings if not h["text"] or len(h["text"].strip()) == 0]
    if empty_headings:
        findings.append({
            "id": "F-REND-008",
            "skill_id": "render-extraction-audit",
            "title": "Empty heading tags detected in markup",
            "severity": "low",
            "impact_area": "ai_discoverability",
            "evidence": f"Found {len(empty_headings)} empty heading elements ({empty_headings[0]['tag']}) with zero text content.",
            "suggested_action": {
                "summary": "Remove empty heading elements or populate them with descriptive section titles.",
                "priority": "low",
                "rationale": "Empty headings confuse automated scrapers and screen readers.",
                "code_fix_example": "<!-- Remove empty tags used solely for CSS spacing -->"
            }
        })

    # 4. Semantic Landmark Coverage
    if landmarks["main"] == 0 and landmarks["article"] == 0:
        findings.append({
            "id": "F-REND-009",
            "skill_id": "render-extraction-audit",
            "title": "Absence of semantic <main> or <article> landmark tags (div soup)",
            "severity": "medium",
            "impact_area": "ai_discoverability",
            "evidence": "Document contains 0 <main> and 0 <article> landmarks. Core content is wrapped entirely in generic <div> containers.",
            "suggested_action": {
                "summary": "Wrap the primary textual substance in a semantic <main> landmark container.",
                "priority": "medium",
                "rationale": "Semantic HTML allows AI parsers to instantly separate substantive content from boilerplate navigation bars, cookie banners, and footers.",
                "code_fix_example": "<main>\n  <h1>Product Overview</h1>\n  <article>...Substantive content...</article>\n</main>"
            }
        })

    # 5. Text-to-HTML Density (Subskill 2.5)
    cleaned = raw_html
    for tag in ["script", "style", "template", "svg", "noscript", "head"]:
        cleaned = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", " ", cleaned, flags=re.DOTALL | re.IGNORECASE)
    clean_text = re.sub(r"<[^>]+>", " ", cleaned)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    raw_len = len(raw_html)
    text_len = len(clean_text)

    if raw_len > 40000 and text_len > 0:
        density_ratio = text_len / raw_len
        if density_ratio < 0.05:
            findings.append({
                "id": "F-REND-010",
                "skill_id": "render-extraction-audit",
                "title": "Excessive markup and script bloat dilutes AI extraction density",
                "severity": "low",
                "impact_area": "ai_discoverability",
                "evidence": f"Text-to-HTML density ratio is {density_ratio:.1%} ({text_len:,} text chars vs {raw_len:,} markup chars). Over 95% of document payload is overhead markup, styles, or inline scripts.",
                "suggested_action": {
                    "summary": "Externalize inline scripts and CSS styles to increase the document text-to-code ratio above 10%.",
                    "priority": "low",
                    "rationale": "High code bloat exhausts AI retrieval context windows and causes LLM tokenizers to drop substantive facts.",
                    "code_fix_example": "<!-- Move inline <style> and tracking <script> blocks to external cached .css and .js files -->"
                }
            })

    return findings
