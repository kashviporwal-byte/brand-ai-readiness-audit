"""
Subskill 3.3: Quotable Definition Sentence Checker
Detects whether a clear, AI-quotable entity definition sentence exists
within the top 200 visible words of the page.
Rule IDs: F-ENT-006, F-ENT-007
"""

import re
from html.parser import HTMLParser


# ── Jargon / marketing buzzword lexicon ─────────────────────────────────────
# Words that, in high density, indicate a vague marketing definition
JARGON_WORDS = frozenset({
    "innovative", "innovation", "innovating", "cutting-edge", "revolutionary",
    "disruptive", "disrupting", "world-class", "best-in-class", "next-generation",
    "next-gen", "state-of-the-art", "transformative", "game-changing",
    "groundbreaking", "paradigm", "paradigm-shifting", "synergy", "synergistic",
    "holistic", "robust", "scalable", "seamless", "frictionless", "end-to-end",
    "best-of-breed", "thought-leader", "thought-leadership", "ecosystem",
    "leverage", "leveraging", "empower", "empowering", "reimagine", "reimagined",
    "reimagining", "solutions-oriented", "future-proof", "future-ready",
    "bleeding-edge", "enterprise-grade", "industry-leading", "market-leading",
    "mission-critical", "best-in-breed", "turnkey", "value-added",
})

# Minimum jargon words to flag a sentence as "marketing-jargon heavy"
JARGON_THRESHOLD = 3

# ── Definition sentence patterns ─────────────────────────────────────────────
# Ordered from most specific to most general; first match wins.
DEFINITION_PATTERNS = [
    # "[Brand/X/We] is/are a/an [type] that/which [verb phrase]..."
    re.compile(
        r'\b[\w][\w\s\-]{0,35}\s+(?:is|are)\s+an?\s+[\w][\w\s\-,]{5,80}'
        r'(?:that|which|to|for)\s+[\w]',
        re.IGNORECASE,
    ),
    # "[X] is the [only/first/leading/...] [noun phrase]"
    re.compile(
        r'\b[\w][\w\s\-]{0,35}\s+(?:is|are)\s+the\s+[\w][\w\s\-,]{5,70}\b',
        re.IGNORECASE,
    ),
    # "[X] provides/enables/delivers/powers/automates [noun phrase]"
    re.compile(
        r'\b[\w][\w\s\-]{0,35}\s+'
        r'(?:provides|enables|delivers|helps|offers|powers|connects|automates|simplifies|transforms)\s+'
        r'[\w][\w\s\-,]{5,80}\b',
        re.IGNORECASE,
    ),
    # "We build/create/make [noun phrase] for [audience]"
    re.compile(
        r'\bWe\s+(?:build|create|make|develop|design|run|operate)\s+[\w][\w\s\-,]{5,80}\b',
        re.IGNORECASE,
    ),
]

# ── HTML parsers ─────────────────────────────────────────────────────────────
# Tags whose text content is never visible to an end-user
_SKIP_TAGS = frozenset({
    "script", "style", "svg", "noscript", "template", "head",
    "nav", "footer", "aside",
})


class VisibleTextExtractor(HTMLParser):
    """
    Extracts only user-visible text, skipping scripts, styles, navigation,
    and footer boilerplate to focus on substantive page content.
    """

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.text_chunks = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)

    def handle_data(self, data):
        if self._skip_depth == 0:
            chunk = data.strip()
            if chunk:
                self.text_chunks.append(chunk)

    def get_text(self):
        return " ".join(self.text_chunks)


# ── Meta description extraction ──────────────────────────────────────────────
# Two patterns handle both attribute orderings
_META_DESC_PATTERNS = [
    re.compile(
        r'<meta\s[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
        re.IGNORECASE,
    ),
    re.compile(
        r'<meta\s[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']description["\']',
        re.IGNORECASE,
    ),
]


def _extract_meta_description(raw_html):
    for pattern in _META_DESC_PATTERNS:
        m = pattern.search(raw_html)
        if m:
            return m.group(1).strip()
    return ""


def _first_n_words(text, n=200):
    words = text.split()
    return " ".join(words[:n]), len(words)


def _jargon_score(text):
    """Returns the count of distinct jargon words found in the text."""
    words = frozenset(re.findall(r'\b[a-z]+(?:-[a-z]+)*\b', text.lower()))
    return len(words & JARGON_WORDS)


def _find_definition_match(text):
    """
    Searches text for the first definition pattern match.
    Returns (matched_string, is_jargon_heavy) or (None, False).
    """
    for pattern in DEFINITION_PATTERNS:
        m = pattern.search(text)
        if m:
            matched = m.group(0).strip()
            return matched, _jargon_score(matched) >= JARGON_THRESHOLD
    return None, False


def check_quotable_definition(raw_html, page_url=""):
    """
    Checks for the presence of a clear, AI-quotable entity definition sentence
    within the first 200 visible words of the page content and meta description.

    Args:
        raw_html (str): Raw HTML of the page.
        page_url  (str): Source URL for evidence strings.

    Returns:
        list[dict]: Standardised finding dicts.
    """
    findings = []
    if not raw_html:
        return findings

    # ── 1. Extract meta description ──────────────────────────────────────────
    meta_desc = _extract_meta_description(raw_html)

    # ── 2. Extract visible body text ─────────────────────────────────────────
    parser = VisibleTextExtractor()
    try:
        parser.feed(raw_html)
    except Exception:
        pass

    full_visible = parser.get_text()
    first_200, total_words = _first_n_words(full_visible, 200)

    # ── 3. Search for definition pattern ─────────────────────────────────────
    # Primary: top 200 words of visible text
    matched, is_jargon_heavy = _find_definition_match(first_200)

    # Fallback: meta description (often the best candidate)
    meta_matched, meta_jargon = _find_definition_match(meta_desc)

    definition_found   = matched is not None or meta_matched is not None
    effective_match    = matched or meta_matched
    effective_jargon   = is_jargon_heavy if matched else meta_jargon

    # ── F-ENT-006: No definition sentence detected at all ────────────────────
    if not definition_found:
        preview = (first_200[:150] + "...") if len(first_200) > 150 else first_200
        findings.append({
            "id": "F-ENT-006",
            "skill_id": "entity-semantics-audit",
            "title": "No clear quotable entity definition sentence found in top 200 words",
            "severity": "high",
            "impact_area": "ai_discoverability",
            "evidence": (
                f"Scanned first {min(200, total_words)} visible words and meta description "
                f"({'present' if meta_desc else 'absent'}). No clear 'X is a/an [type] that "
                f"[provides/does]...' definition pattern detected. "
                f"Top-200-word preview: \"{preview}\""
            ),
            "suggested_action": {
                "summary": (
                    "Add a concise, self-contained definition sentence in the first paragraph "
                    "of the homepage and in the meta description."
                ),
                "priority": "high",
                "rationale": (
                    "AI answer engines (ChatGPT, Perplexity, Claude) extract direct quotes "
                    "from web pages to synthesize answers. A clear 'X is a [type] that [does Y]' "
                    "pattern is the highest-probability quotable sentence for brand question "
                    "answering. Pages without one are described by AI using third-party sources, "
                    "increasing hallucination risk."
                ),
                "code_fix_example": (
                    "<!-- Homepage hero — first visible sentence: -->\n"
                    "<h1>Acme Cloud Platform</h1>\n"
                    "<p>Acme is an enterprise workflow automation platform that connects "
                    "distributed teams, APIs, and data pipelines in a single low-code "
                    "environment — used by 1,200 Fortune 500 teams.</p>\n\n"
                    "<!-- meta description (equally important): -->\n"
                    "<meta name=\"description\" content=\"Acme is an enterprise workflow "
                    "automation platform that reduces operational latency by 70% for "
                    "Fortune 500 companies.\">"
                ),
            },
        })

    # ── F-ENT-007: Definition found but jargon-heavy ─────────────────────────
    elif effective_jargon:
        excerpt = (effective_match[:120] + "...") if len(effective_match) > 120 else effective_match
        findings.append({
            "id": "F-ENT-007",
            "skill_id": "entity-semantics-audit",
            "title": "Entity definition sentence detected but contains excessive marketing jargon",
            "severity": "medium",
            "impact_area": "ai_discoverability",
            "evidence": (
                f"A definition-like sentence was found but scored ≥{JARGON_THRESHOLD} "
                f"jargon/buzzword terms, reducing AI quotability and citation specificity. "
                f"Excerpt: \"{excerpt}\""
            ),
            "suggested_action": {
                "summary": (
                    "Replace vague superlatives and buzzwords with concrete, factual, "
                    "and specific claims including measurable outcomes."
                ),
                "priority": "medium",
                "rationale": (
                    "AI citation engines (Perplexity, SearchGPT) prefer precise, falsifiable "
                    "statements over marketing language. Sentences containing 'innovative', "
                    "'cutting-edge', or 'world-class' score low on citation probability compared "
                    "to sentences containing quantified outcomes ('reduces latency by 70%')."
                ),
                "code_fix_example": (
                    "<!-- Instead of: -->\n"
                    "<p>We deliver innovative, cutting-edge, best-in-class enterprise "
                    "solutions that transform businesses.</p>\n\n"
                    "<!-- Write: -->\n"
                    "<p>Acme automates order fulfilment workflows for e-commerce companies, "
                    "reducing processing errors by 94% and fulfilment time from 48 hours "
                    "to under 4 hours.</p>"
                ),
            },
        })

    return findings
