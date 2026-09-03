"""
Subskill 4.3: Information Density & Summarization Resilience Evaluator (Appendix F)
Measures the ratio of substantive factual content versus marketing fluff/buzzwords
and simulates AI extractive summarization compression to detect fact-retention drop-off.
Rule IDs: F-FRSH-006, F-FRSH-007
"""

import re
from html.parser import HTMLParser


# ── Buzzword / Marketing Fluff Corpus ────────────────────────────────────────
# Exact phrase matches (lowercased). Matched as whole words/phrases in tokenized content.

BUZZWORD_PHRASES = frozenset([
    # Temporal hype
    "next-generation", "next generation", "next-gen", "next gen",
    "cutting-edge", "cutting edge", "state-of-the-art", "state of the art",
    "future-proof", "future proof",
    # Superlative hype
    "revolutionary", "revolution", "game-changing", "game changing",
    "game changer", "groundbreaking", "ground-breaking",
    "unprecedented", "unparalleled", "unmatched", "unrivaled", "unrivalled",
    "world-class", "world class", "best-in-class", "best in class",
    "best-of-breed", "best of breed", "industry-leading", "industry leading",
    "market-leading", "market leading", "award-winning", "award winning",
    # Consulting / MBA jargon
    "paradigm shift", "paradigm-shifting", "paradigm shifting",
    "synergy", "synergize", "synergistic", "synergies",
    "leverage synergies", "core competencies", "value proposition" , "go-to-market",
    "key takeaways", "low-hanging fruit", "move the needle", "boil the ocean",
    "circle back", "deep dive", "bandwidth", "alignment", "scalability",
    "ecosystem", "holistic", "end-to-end solution", "360-degree",
    "thought leader", "thought leadership", "industry leader",
    "market leader", "visionary", "disruptor",
    # UX vagueness
    "seamless", "frictionless", "effortless", "intuitive", "easy-to-use",
    "user-friendly", "hassle-free", "out-of-the-box",
    # Motivational vagueness
    "empower", "empowering", "empowers", "unleash", "unlock", "unlock the power",
    "unlock your potential", "transform your", "reimagine", "reshape",
    "ignite", "accelerate your journey", "supercharge",
    # Startup clichés
    "innovative", "innovate", "innovation", "disruptive", "disrupt", "disrupting",
    "game-changer", "bleeding edge", "on the cutting edge",
    "rethink", "reinvent", "reshape",
    # Vague scope
    "comprehensive solution", "all-in-one", "one-stop-shop", "one stop shop",
    "turnkey", "plug-and-play", "full-stack solution",
    "enterprise-grade", "enterprise grade", "bespoke",
])

# Regex patterns for buzzword detection (for multi-word phrases with flexible spacing)
_BUZZWORD_PATTERNS = [
    re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
    for phrase in sorted(BUZZWORD_PHRASES, key=len, reverse=True)  # Longest first
]

# ── Substantive Token Patterns ────────────────────────────────────────────────

# Numbers, percentages, currency
_NUMERIC_RE = re.compile(r"\b\d[\d,./]*(?:%|ms|kb|mb|gb|tb|rpm|rps|vCPU)?\b", re.IGNORECASE)

# Technical terminology: strict acronyms, version numbers, API path patterns
# NOTE: NOT re.IGNORECASE — we want uppercase-only acronyms (API, REST, AES, TLS)
_TECHNICAL_RE = re.compile(
    r"\b(?:"
    r"[A-Z][A-Z0-9]{1,}(?:[-_][A-Z0-9]+)*"   # True uppercase acronyms: API, REST, TLS, AES256, CI-CD
    r"|v\d+(?:\.\d+){1,3}"                     # Version numbers: v2.0, v1.0.3 (require dot)
    r"|https?://[^\s<>\"']{4,}"                # URLs as substantive references
    r")"
)

# Domain-specific technical verbs (positive substantive indicators)
_TECHNICAL_VERBS_RE = re.compile(
    r"\b(?:encrypt|decrypt|authenticate|authorize|deploy|monitor|validate|process|compute|"
    r"replicate|synchronize|index|compress|cache|stream|partition|shard|migrate|"
    r"orchestrate|containerize|provision|configure|parse|serialize|ingest|emit|"
    r"throttle|route|balance|detect|classify|segment|aggregate|transform|batch)\w*\b",
    re.IGNORECASE,
)

# Domain-specific technical nouns and software concepts
_TECHNICAL_TERMS_RE = re.compile(
    r"\b(?:module|function|class|method|syntax|variable|parameter|argument|attribute|"
    r"library|package|runtime|compiler|interpreter|algorithm|protocol|exception|"
    r"endpoint|payload|handler|database|schema|query|latency|throughput|bandwidth|"
    r"interface|namespace|callback|iterator|generator|coroutine|thread|process)\w*\b",
    re.IGNORECASE,
)

# Stopwords — NOT substantive, NOT buzzwords: just grammar/functional tokens
_STOPWORDS = frozenset([
    "the", "a", "an", "and", "or", "but", "in", "of", "for", "to", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "could", "should", "may", "might", "shall",
    "that", "this", "these", "those", "it", "its", "we", "our", "us", "you",
    "your", "they", "their", "them", "he", "she", "his", "her", "with", "from",
    "at", "by", "on", "as", "into", "through", "during", "before", "after",
    "above", "below", "between", "out", "off", "over", "under", "again",
    "then", "once", "any", "all", "both", "each", "few", "more", "most",
    "not", "no", "so", "yet", "than", "when", "where", "who", "which", "how",
    "about", "also", "just", "can", "up", "if",
])

# Minimum words for a page to be evaluated for density
_MIN_WORDS_FOR_DENSITY = 40

# Density thresholds — per spec 4.3:
# High   if density < 30% on core documentation/product pages
# Medium if density between 30%–45%
_DENSITY_HIGH_RISK = 30.0    # Below 30% → F-FRSH-006 High
_DENSITY_MEDIUM_RISK = 45.0  # 30%–45% → F-FRSH-006 Medium
_BUZZWORD_RATIO_THRESHOLD = 0.12  # >12% buzzword concentration → F-FRSH-007


# ── HTML Parser ───────────────────────────────────────────────────────────────

class _ContentParser(HTMLParser):
    """
    Extracts clean visible body text excluding navigation, footer,
    header, script, style, and aside boilerplate regions.
    """

    # Tags whose content is excluded from density analysis
    EXCLUDE_TAGS = {"nav", "script", "style", "noscript", "header", "footer",
                    "aside", "form", "button", "select", "option"}

    def __init__(self):
        super().__init__()
        self.content_text = ""
        self._exclude_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.EXCLUDE_TAGS:
            self._exclude_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() in self.EXCLUDE_TAGS and self._exclude_depth > 0:
            self._exclude_depth -= 1

    def handle_data(self, data):
        if self._exclude_depth == 0:
            stripped = data.strip()
            if stripped:
                self.content_text += " " + stripped


# ── Core Analysis Functions ───────────────────────────────────────────────────

def _tokenize(text):
    """Simple whitespace + punctuation tokenizer. Returns list of lowercase tokens."""
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9'_-]*[A-Za-z0-9]|[A-Za-z0-9]", text)
    return [t.lower() for t in tokens]


def _count_buzzword_tokens(text):
    """
    Counts the number of buzzword phrase occurrences in the text.
    Returns (count, list_of_matched_phrases).
    """
    matched = []
    remaining = text.lower()
    for pattern in _BUZZWORD_PATTERNS:
        for m in pattern.finditer(remaining):
            matched.append(m.group(0))
    return len(matched), matched[:10]  # Cap sample list for evidence string


def _count_substantive_tokens(text):
    """
    Counts substantive factual tokens: numbers, acronyms, technical verbs, terms, URLs.
    Returns count.
    """
    count = 0
    count += len(_NUMERIC_RE.findall(text))
    count += len(_TECHNICAL_RE.findall(text))
    count += len(_TECHNICAL_VERBS_RE.findall(text))
    count += len(_TECHNICAL_TERMS_RE.findall(text))
    return count


def _simulate_summarization(text, retention_ratio=0.30):
    """
    Simulates extractive AI summarization by retaining the top-scoring sentences
    (ranked by factual token density) up to `retention_ratio` of total word count.

    Returns (retained_word_count, retained_substantive_count, total_substantive_count).
    """
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    if not sentences:
        return 0, 0, 0

    total_words = len(text.split())
    target_words = max(1, int(total_words * retention_ratio))

    # Score each sentence by substantive density
    scored = []
    for sent in sentences:
        words = sent.split()
        if not words:
            continue
        subst = _count_substantive_tokens(sent)
        density = subst / max(len(words), 1)
        scored.append((density, len(words), subst, sent))

    # Sort by density descending (extractive summarization picks densest)
    scored.sort(key=lambda x: x[0], reverse=True)

    retained_words = 0
    retained_subst = 0
    for density, word_count, subst, sent in scored:
        if retained_words >= target_words:
            break
        retained_words += word_count
        retained_subst += subst

    total_subst = sum(s for _, _, s, _ in scored)
    return retained_words, retained_subst, total_subst


def _make_finding(rule_id, title, severity, evidence, summary, priority, rationale, code_fix):
    return {
        "id":         rule_id,
        "skill_id":   "freshness-corroboration",
        "title":      title,
        "severity":   severity,
        "impact_area": "ai_discoverability",
        "evidence":   evidence,
        "suggested_action": {
            "summary":          summary,
            "priority":         priority,
            "rationale":        rationale,
            "code_fix_example": code_fix,
        },
    }


# ── Main Public Function ──────────────────────────────────────────────────────

def check_information_density(raw_html, page_url=""):
    """
    Evaluates information density and AI summarization resilience (Appendix F).

    Args:
        raw_html (str): The raw HTML of the page.
        page_url (str): URL used in evidence strings.

    Returns:
        list[dict]: Findings conforming to report_schema.json.
    """
    if not raw_html or not raw_html.strip():
        return []

    parser = _ContentParser()
    try:
        parser.feed(raw_html)
    except Exception:
        return []

    content_text = parser.content_text.strip()
    if not content_text:
        return []

    all_tokens = _tokenize(content_text)
    total_tokens = len(all_tokens)
    if total_tokens < _MIN_WORDS_FOR_DENSITY:
        return []

    # Count content tokens (non-stopword tokens)
    content_tokens = [t for t in all_tokens if t not in _STOPWORDS and len(t) > 1]
    content_token_count = len(content_tokens)
    if content_token_count == 0:
        return []

    # Count buzzwords and substantive tokens
    buzzword_count, buzzword_samples = _count_buzzword_tokens(content_text)
    substantive_count = _count_substantive_tokens(content_text)

    # Information Density Score
    # Denominator: content tokens (all non-stopword tokens)
    density_score = (substantive_count / content_token_count) * 100.0

    # Buzzword ratio
    buzzword_ratio = buzzword_count / content_token_count

    findings = []

    # ── F-FRSH-006: Low Information Density ──────────────────────────────────
    if density_score < _DENSITY_HIGH_RISK:
        if buzzword_ratio < 0.02:
            severity = "medium"
            density_interpretation = "moderate technical density (low buzzwords)"
        else:
            severity = "high"
            density_interpretation = "critically low (high fluff disparity)"
    elif density_score < _DENSITY_MEDIUM_RISK:
        severity = "medium"
        density_interpretation = "below the recommended threshold"
    else:
        severity = None

    if severity:
        # Simulate summarization impact
        _, ret_subst, total_subst = _simulate_summarization(content_text)
        retention_pct = (ret_subst / max(total_subst, 1)) * 100

        findings.append(_make_finding(
            rule_id="F-FRSH-006",
            title=f"Low information density: {density_score:.1f}% substantive content ({density_interpretation})",
            severity=severity,
            evidence=(
                f"Page '{page_url or 'this URL'}' has an information density score of "
                f"{density_score:.1f}% (target: ≥ 45%). "
                f"Total content tokens: {content_token_count}; "
                f"Substantive factual tokens: {substantive_count}; "
                f"Marketing/fluff tokens: {buzzword_count}. "
                f"Simulated AI extractive summarization retains ~{retention_pct:.0f}% of "
                f"factual substance — low density means genuine facts are drowned out by "
                "promotional noise during AI compression."
            ),
            summary=(
                "Replace vague marketing language with concrete specifications, "
                "measurable data, and technically precise descriptions."
            ),
            priority=severity,
            rationale=(
                "AI summarizers (ChatGPT, Claude, Perplexity) extract the densest factual "
                "sentences first. Low-density pages see their key facts dropped during "
                "compression, leaving only generic marketing phrases in AI answers — "
                "making the brand appear undifferentiated."
            ),
            code_fix=(
                '<!-- BEFORE (low density): -->\n'
                '<p>Our revolutionary, next-generation platform empowers enterprises to '
                'unleash synergistic value with seamless, best-in-class solutions.</p>\n\n'
                '<!-- AFTER (high density): -->\n'
                '<p>Acme Cloud processes 10 billion API events per day with p99 latency '
                'of 4ms, using AES-256 encryption at rest and TLS 1.3 in transit, '
                'across 40 data centers in 15 countries.</p>'
            ),
        ))

    # ── F-FRSH-007: Excessive Buzzword Dilution ───────────────────────────────
    if buzzword_ratio > _BUZZWORD_RATIO_THRESHOLD and buzzword_count >= 3:
        top_buzzwords = list(dict.fromkeys(buzzword_samples))[:6]  # Deduplicated sample
        findings.append(_make_finding(
            rule_id="F-FRSH-007",
            title=f"Excessive marketing buzzword dilution: {buzzword_count} fluff phrases detected",
            severity="medium",
            evidence=(
                f"Page contains {buzzword_count} marketing buzzword/fluff phrase occurrences "
                f"({buzzword_ratio * 100:.1f}% of content tokens, threshold: "
                f"{_BUZZWORD_RATIO_THRESHOLD * 100:.0f}%). "
                f"Top buzzwords detected: {', '.join(repr(b) for b in top_buzzwords)}. "
                "High buzzword concentration reduces AI summarization resilience — AI models "
                "extract facts, not promotional language, making buzzword-heavy pages "
                "appear substance-free in AI-synthesized answers."
            ),
            summary=(
                "Audit and replace the highest-frequency marketing buzzwords with "
                "specific, factual, and measurable language."
            ),
            priority="medium",
            rationale=(
                "Appendix F defines 'summarization resilience' as the ability of key brand "
                "facts to survive AI compression. Buzzwords are filtered out early by "
                "AI extractive summarizers because they carry zero factual signal. "
                "Pages exceeding 12% buzzword concentration typically retain fewer than "
                "15% of their brand claims in AI-generated email or chat digests."
            ),
            code_fix=(
                '<!-- Replace marketing phrases with factual alternatives: -->\n\n'
                '  "revolutionary platform" → "event-streaming platform processing 10B events/day"\n'
                '  "best-in-class security" → "SOC 2 Type II certified, FIPS 140-2 validated"\n'
                '  "seamless integration"  → "REST and GraphQL APIs with < 200ms p95 response"\n'
                '  "next-generation AI"    → "GPT-4 Turbo fine-tuned on domain-specific data"\n'
                '  "empowers teams"        → "reduces alert triage time from 45 min to 8 min"'
            ),
        ))

    return findings
