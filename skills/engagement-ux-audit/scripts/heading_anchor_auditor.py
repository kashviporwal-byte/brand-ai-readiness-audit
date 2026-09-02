"""
Subskill 5.1: Heading Anchor & Deep-Link Auditor
Audits section headings (<h2>, <h3>) for HTML id attributes that enable
AI assistant citations to jump directly to the relevant fragment.
Uses a self-healing DOM tag stack to exclude sidebar navigation labels
and footer columns from the ratio, even if tags are malformed or unclosed.
Rule IDs: F-ENG-001, F-ENG-002, F-ENG-008
"""

import re
from html.parser import HTMLParser


GENERIC_IDS = frozenset({
    "section", "content", "title", "header", "heading", "item", "block",
    "main", "container", "box", "text", "body", "post", "article",
    "div", "wrap", "wrapper"
})

VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr"
})

CHROME_TAGS = frozenset({"nav", "footer", "aside"})


class HeadingAnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.headings = []         # Content headings only
        self.tag_stack = []        # list of {"tag": str, "is_chrome": bool}
        self.all_anchor_ids = set()
        self.dead_fragment_links = []
        self._current_heading = None
        self._heading_text = []

    @property
    def in_chrome(self):
        return any(entry["is_chrome"] for entry in self.tag_stack)

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        attr_dict = {k.lower(): (v or "").strip() for k, v in attrs}

        elem_id = attr_dict.get("id", "")
        elem_name = attr_dict.get("name", "")
        if elem_id:
            self.all_anchor_ids.add(elem_id.lower())
        if elem_name:
            self.all_anchor_ids.add(elem_name.lower())

        is_void = tag_lower in VOID_TAGS
        cls = attr_dict.get("class", "").lower()
        is_chrome_tag = (tag_lower in CHROME_TAGS) or ("nav" in cls.split() or "sidebar" in cls.split() or "footer" in cls.split())

        # Implicit recovery: If entering <main> or <article>, any unclosed <nav> is popped
        # Implicit recovery: By W3C specification, <main> cannot be a descendant of <nav>.
        if tag_lower == "main":
            self.tag_stack = [e for e in self.tag_stack if e["tag"] != "nav"]

        if not is_void:
            self.tag_stack.append({
                "tag": tag_lower,
                "is_chrome": is_chrome_tag
            })

        if tag_lower in ("h2", "h3"):
            # Only record content headings; ignore sidebar nav labels or footer columns
            if not self.in_chrome:
                self._current_heading = {
                    "tag": tag_lower,
                    "id": elem_id or elem_name,
                    "has_nested_anchor": False,
                    "text": ""
                }
                self._heading_text = []

        elif self._current_heading and tag_lower == "a":
            a_id = elem_id or elem_name
            if a_id:
                self._current_heading["id"] = a_id
                self._current_heading["has_nested_anchor"] = True

        elif tag_lower == "a":
            href = attr_dict.get("href", "")
            if href == "#" or href == "#top" or href.startswith("javascript:void"):
                self.dead_fragment_links.append(href)

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower in VOID_TAGS:
            return

        # Self-healing backwards pop
        tags_on_stack = [entry["tag"] for entry in self.tag_stack]
        if tag_lower in tags_on_stack:
            while self.tag_stack:
                popped = self.tag_stack.pop()
                if popped["tag"] == tag_lower:
                    break

        if tag_lower in ("h2", "h3") and self._current_heading:
            self._current_heading["text"] = " ".join("".join(self._heading_text).split())
            self.headings.append(self._current_heading)
            self._current_heading = None
            self._heading_text = []

    def handle_data(self, data):
        if self._current_heading:
            self._heading_text.append(data)


def check_heading_anchors(raw_html, page_url=""):
    findings = []
    if not raw_html:
        return findings

    parser = HeadingAnchorParser()
    try:
        parser.feed(raw_html)
    except Exception:
        pass

    headings = parser.headings
    # Only audit pages that have multiple major content sections
    if len(headings) < 2:
        return findings

    headings_without_id = []
    seen_ids = {}
    duplicate_ids = []
    generic_ids = []

    for h in headings:
        hid = h["id"]
        htext = h["text"]
        tag = h["tag"].upper()

        if not hid:
            headings_without_id.append(f"{tag}: \'{htext[:40]}\'" if htext else tag)
        else:
            hid_lower = hid.lower()
            if hid_lower in seen_ids:
                duplicate_ids.append(hid)
            else:
                seen_ids[hid_lower] = htext

            # Check for generic/non-descriptive IDs (including numbered like section-1, content-2)
            clean_tokens = {t for t in re.split(r"[-_0-9]+", hid_lower) if t}
            if hid_lower in GENERIC_IDS or (clean_tokens and clean_tokens.issubset(GENERIC_IDS)):
                generic_ids.append(hid)

    # 1. F-ENG-001: Missing Heading Anchor IDs
    if headings_without_id:
        ratio_missing = len(headings_without_id) / len(headings)
        if ratio_missing > 0.35:
            preview = "; ".join(headings_without_id[:3])
            suffix = f" (+{len(headings_without_id) - 3} more)" if len(headings_without_id) > 3 else ""
            findings.append({
                "id": "F-ENG-001",
                "skill_id": "engagement-ux-audit",
                "title": "Major section headings lack anchor IDs for AI deep-link citations",
                "severity": "high",
                "impact_area": "on_site_engagement",
                "evidence": (
                    f"Audited {len(headings)} content section headings (H2/H3); {len(headings_without_id)} "
                    f"({ratio_missing:.1%}) lack an HTML 'id' attribute. AI assistant citation links "
                    f"cannot deep-link directly to relevant sections. Unanchored samples: [{preview}{suffix}]."
                ),
                "suggested_action": {
                    "summary": "Add unique, URL-safe 'id' attributes to all <h2> and <h3> section headings.",
                    "priority": "high",
                    "rationale": (
                        "When AI assistants quote a specific feature or benchmark, they generate URL fragment "
                        "links (e.g. #benchmark-results). Without heading IDs, referred users land at the top "
                        "of the page, feel disoriented, and immediately bounce."
                    ),
                    "code_fix_example": (
                        "<!-- Before: -->\n"
                        "<h2>Enterprise Security & Compliance</h2>\n\n"
                        "<!-- After: -->\n"
                        "<h2 id=\"enterprise-security\">Enterprise Security & Compliance</h2>"
                    )
                }
            })

    # 2. F-ENG-002: Duplicate or Generic Heading Anchor IDs
    if duplicate_ids or generic_ids:
        problem_samples = []
        if duplicate_ids:
            problem_samples.append(f"Duplicates: {duplicate_ids[:3]}")
        if generic_ids:
            problem_samples.append(f"Generic non-descriptive: {generic_ids[:3]}")
        evidence_str = "; ".join(problem_samples)

        findings.append({
            "id": "F-ENG-002",
            "skill_id": "engagement-ux-audit",
            "title": "Duplicate or non-descriptive heading anchor IDs create citation collisions",
            "severity": "medium",
            "impact_area": "on_site_engagement",
            "evidence": (
                f"Found problematic heading IDs that degrade AI fragment routing: {evidence_str}."
            ),
            "suggested_action": {
                "summary": "Ensure heading IDs are globally unique, descriptive slugs derived from the heading text.",
                "priority": "medium",
                "rationale": (
                    "Generic IDs like 'section-1' or duplicate IDs cause browsers to jump to the wrong content, "
                    "breaking user expectation when arriving from a specific AI citation."
                ),
                "code_fix_example": (
                    "<h2 id=\"pricing-calculator\">Pricing Calculator</h2>\n"
                    "<h2 id=\"faq-billing\">Billing FAQ</h2>"
                )
            }
        })

    # 3. F-ENG-008: Excessive Dead Fragment Links
    if len(parser.dead_fragment_links) >= 3:
        findings.append({
            "id": "F-ENG-008",
            "skill_id": "engagement-ux-audit",
            "title": "Interactive buttons and links rely on dead anchor fragments (href=\"#\")",
            "severity": "low",
            "impact_area": "on_site_engagement",
            "evidence": (
                f"Detected {len(parser.dead_fragment_links)} anchor link(s) using placeholder 'href="#"' "
                f"or 'href="#top"'. Clicking these elements resets scroll position without performing navigation."
            ),
            "suggested_action": {
                "summary": "Replace dummy href='#' placeholders with proper semantic <button> elements or valid target routes.",
                "priority": "low",
                "rationale": (
                    "Placeholder hash links break accessibility and cause referred visitors to lose their reading "
                    "position when clicking interactive UI elements."
                ),
                "code_fix_example": (
                    "<!-- Instead of: <a href=\"#\" class=\"btn\">Action</a> -->\n"
                    "<button type=\"button\" class=\"btn\">Action</button>"
                )
            }
        })

    return findings
