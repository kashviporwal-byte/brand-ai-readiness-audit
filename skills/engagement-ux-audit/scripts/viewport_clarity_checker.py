"""
Subskill 5.2: Above-The-Fold Value Clarity Auditor
Audits the initial viewport / hero section for immediate visitor orientation:
- Clear headline and value proposition (3-second orientation rule)
- Visible, actionable Call-To-Action (CTA) in the hero (excluding navigation chrome)
Uses a self-healing DOM tag stack to handle unclosed tags without losing track
of the true above-the-fold content boundary.
Rule IDs: F-ENG-003, F-ENG-004
"""

import re
from html.parser import HTMLParser


ACTION_CTA_PATTERNS = re.compile(
    r"\b(start|get started|try|try for free|sign up|join|request demo|book demo|contact us|"
    r"download|install|explore|view docs|learn more|see pricing|talk to sales)\b",
    re.IGNORECASE
)

VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr"
})


class ViewportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tag_stack = []        # list of {"tag": str, "is_nav": bool, "is_footer": bool, "is_hero": bool}
        self.above_the_fold_active = True
        self.word_budget = 0
        self.hero_text = []
        self.h1_texts = []
        self.cta_elements = []
        self.all_buttons = []

    @property
    def in_nav(self):
        return any(entry["is_nav"] for entry in self.tag_stack)

    @property
    def in_footer(self):
        return any(entry["is_footer"] for entry in self.tag_stack)

    @property
    def in_hero(self):
        return any(entry["is_hero"] for entry in self.tag_stack)

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        attr_dict = {k.lower(): (v or "").strip() for k, v in attrs}
        cls = attr_dict.get("class", "").lower()
        elem_id = attr_dict.get("id", "").lower()
        is_void = tag_lower in VOID_TAGS

        is_nav_tag = tag_lower == "nav" or "nav" in cls.split()
        is_footer_tag = tag_lower in ("footer", "aside") or "footer" in cls.split()

        is_explicit_hero = any(k in cls or k in elem_id for k in ("hero", "banner", "jumbotron", "lead"))
        # Implicit recovery: By W3C specification, <main> cannot be a descendant of <nav>.
        # Additionally, an explicit hero element (e.g. <header class="hero">) indicates the start
        # of the site hero, popping any orphaned unclosed <nav>.
        # Legitimate mega-menu headers (<header> with no hero class) and <article> tags remain inside <nav>.
        if tag_lower == "main" or (is_explicit_hero and self.in_nav):
            self.tag_stack = [e for e in self.tag_stack if not e["is_nav"]]

        if is_footer_tag:
            self.above_the_fold_active = False

        # End above-the-fold region if we hit secondary content headers outside hero
        if not self.in_hero and tag_lower in ("h2", "h3") and self.word_budget > 40:
            self.above_the_fold_active = False

        is_hero_element = (
            (tag_lower == "header" and not self.in_nav) or
            any(k in cls or k in elem_id for k in ("hero", "banner", "intro", "jumbotron", "lead"))
        )

        if not is_void:
            self.tag_stack.append({
                "tag": tag_lower,
                "is_nav": is_nav_tag,
                "is_footer": is_footer_tag,
                "is_hero": is_hero_element
            })

        # Detect Actionable CTAs (Must be above-the-fold and NOT inside top nav or footer)
        is_cta_eligible = self.above_the_fold_active and (not self.in_nav) and (not self.in_footer)

        if tag_lower in ("button", "input"):
            val = attr_dict.get("value", "")
            aria = attr_dict.get("aria-label", "")
            btn_label = val or aria or tag_lower
            self.all_buttons.append(btn_label)
            if is_cta_eligible:
                self.cta_elements.append(btn_label)

        elif tag_lower == "a":
            aria = attr_dict.get("aria-label", "")
            has_cta_class = any(k in cls for k in ("btn", "button", "cta", "action"))
            if is_cta_eligible and has_cta_class:
                self.cta_elements.append(aria or "btn-link")

        if tag_lower == "h1" and not self.in_nav:
            self.h1_texts.append("")

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower in VOID_TAGS:
            return

        # Self-healing backwards pop
        tags_on_stack = [entry["tag"] for entry in self.tag_stack]
        if tag_lower in tags_on_stack:
            while self.tag_stack:
                popped = self.tag_stack.pop()
                if popped["is_hero"] and self.word_budget >= 30:
                    self.above_the_fold_active = False
                if popped["tag"] == tag_lower:
                    break

    def handle_data(self, data):
        txt = data.strip()
        if not txt:
            return

        # Do not let navigation links pollute hero value-prop text or H1 headline
        if self.in_nav or self.in_footer:
            return

        words_in_chunk = len(txt.split())
        self.word_budget += words_in_chunk

        if self.word_budget > 130 and not self.in_hero:
            self.above_the_fold_active = False

        if self.h1_texts and self.h1_texts[-1] == "":
            self.h1_texts[-1] = txt

        if self.above_the_fold_active or self.in_hero:
            self.hero_text.append(txt)
            if ACTION_CTA_PATTERNS.search(txt):
                self.cta_elements.append(txt)


def check_viewport_clarity(raw_html, page_url=""):
    findings = []
    if not raw_html:
        return findings

    # Pre-clean raw HTML: strip <head>, <script>, <style>, <svg>, <noscript>, <template>
    # contents so JSON-LD schemas and inline scripts/styles don't pollute hero text or word budget
    clean_html = re.sub(
        r'<(?:head|script|style|svg|noscript|template)\b[^>]*>.*?</(?:head|script|style|svg|noscript|template)>',
        '',
        raw_html,
        flags=re.IGNORECASE | re.DOTALL
    )

    parser = ViewportParser()
    try:
        parser.feed(clean_html)
    except Exception:
        pass

    hero_words = " ".join(parser.hero_text).split()
    first_100_words = " ".join(hero_words[:100])
    h1_text = parser.h1_texts[0] if parser.h1_texts else ""

    # 1. F-ENG-003: Weak Above-The-Fold Value Clarity (The 3-Second Rule)
    has_substantive_h1 = len(h1_text.split()) >= 3 and len(h1_text) >= 12
    vague_slogan_patterns = [
        re.compile(r"^(welcome|home|hello|start|the future|innovate|tomorrow)$", re.IGNORECASE),
        re.compile(r"^(create at the highest level|think different|just do it|unleash your potential|unleash tomorrow)$", re.IGNORECASE)
    ]
    is_vague_slogan = any(p.search(h1_text.strip()) for p in vague_slogan_patterns)

    if not has_substantive_h1 or is_vague_slogan:
        preview = f"\'{h1_text}\'" if h1_text else "None detected"
        findings.append({
            "id": "F-ENG-003",
            "skill_id": "engagement-ux-audit",
            "title": "Above-the-fold hero section lacks a descriptive value proposition (fails 3-second rule)",
            "severity": "high",
            "impact_area": "on_site_engagement",
            "evidence": (
                f"Primary hero heading ({preview}) is missing or consists of an abstract marketing slogan. "
                f"Visitors referred from AI citations need immediate confirmation within 3 seconds of who "
                f"the brand is and what problem it solves. Hero text preview: \'{first_100_words[:120]}...\'"
            ),
            "suggested_action": {
                "summary": "State a clear, descriptive value proposition in the primary above-the-fold headline.",
                "priority": "high",
                "rationale": (
                    "Users referred by AI assistant citations arrive with high intent but zero brand loyalty. "
                    "If the hero section fails to explain the product in 3 seconds, bounce rates increase drastically."
                ),
                "code_fix_example": (
                    "<!-- Instead of: <h1>Unleash Tomorrow</h1> -->\n"
                    "<h1>Real-Time Fraud Detection Engine for Payment Processors</h1>\n"
                    "<p class=\"hero-subhead\">Stop 99.8% of unauthorized transactions with sub-10ms AI decisioning.</p>"
                )
            }
        })

    # 2. F-ENG-004: Missing Above-The-Fold Call-To-Action (CTA)
    if not parser.cta_elements:
        findings.append({
            "id": "F-ENG-004",
            "skill_id": "engagement-ux-audit",
            "title": "Initial viewport lacks a visible, prominent Call-To-Action (CTA)",
            "severity": "medium",
            "impact_area": "on_site_engagement",
            "evidence": (
                f"Found 0 actionable Call-To-Action elements (e.g. 'Start Free Trial', 'Book Demo', 'Sign Up') "
                f"in the above-the-fold viewport. Total page buttons found: {len(parser.all_buttons)}."
            ),
            "suggested_action": {
                "summary": "Place a high-contrast, primary conversion button visibly in the initial hero viewport.",
                "priority": "medium",
                "rationale": (
                    "Visitors arriving from AI citations have verified the answer and are ready for the next action. "
                    "A missing above-the-fold CTA forces needless scrolling and forfeits referral conversions."
                ),
                "code_fix_example": (
                    "<div class=\"hero-actions\">\n"
                    "  <a href=\"/signup\" class=\"btn btn-primary\">Get Started Free</a>\n"
                    "  <a href=\"/docs\" class=\"btn btn-secondary\">Explore Documentation</a>\n"
                    "</div>"
                )
            }
        })

    return findings
