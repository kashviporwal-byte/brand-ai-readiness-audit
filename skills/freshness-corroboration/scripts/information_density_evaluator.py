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


def _evaluate_weighted_tokens(text):
    """
    Evaluates substantive tokens across all non-stopword content tokens.
    Default content words get 1.0 weight.
    Numeric / Technical terms get 1.5x bonus weight.
    Capitalized Proper Nouns / Named Entities get 1.2x bonus weight.
    Buzzwords get 0.0 weight.
    Returns (weighted_substantive_score, raw_substantive_count).
    """
    tokens = re.findall(r"\b[A-Za-z0-9][A-Za-z0-9'_-]*[A-Za-z0-9]\b|\b[A-Za-z0-9]\b", text)
    weighted_score = 0.0
    raw_substantive_count = 0

    for tok in tokens:
        low = tok.lower()
        if low in _STOPWORDS or len(low) <= 1:
            continue
        # Bucket A only: numeric/technical/proper-noun tokens are the sole positive
        # signal. Ordinary non-buzzword filler words ("team", "helps", "people",
        # "matters") get 0.0 — they are neither fluff nor fact, and defaulting them
        # to a positive weight is what caused pure buzzword pages to score as
        # "dense" (this was the actual v2/v3 regression). This keeps genuinely
        # factual non-tech prose (numbers, named entities) scoring correctly
        # without rewarding generic filler just for not being on the buzzword list.
        weight = 0.0
        if (_NUMERIC_RE.match(tok) or _TECHNICAL_RE.match(tok) or
                _TECHNICAL_VERBS_RE.match(tok) or _TECHNICAL_TERMS_RE.match(tok)):
            weight = 1.5
        elif tok[0].isupper():
            weight = 1.2

        weighted_score += weight
        if weight > 0:
            raw_substantive_count += 1

    return weighted_score, raw_substantive_count


def _count_substantive_tokens(text):
    """
    Counts substantive factual tokens: numbers, acronyms, technical verbs, terms, URLs.
    Returns count.
    """
    w_score, raw_count = _evaluate_weighted_tokens(text)
    return int(raw_count)


def check_tldr_summary_block(raw_html, page_url=""):
    """
    F-FRSH-008: Missing TL;DR or Key Takeaways Summary Block on Long-Form Content.
    """
    if not raw_html:
        return []
    clean_text = re.sub(r'<[^>]+>', ' ', raw_html)
    words = clean_text.split()
    if len(words) < 800:
        return []

    has_tldr = bool(re.search(
        r'<(?:h[1-4]|div|section)\b[^>]*>(?:[^<]*\b(?:tl;?dr|key takeaways|summary|at a glance|executive summary)\b[^<]*)</(?:h[1-4]|div|section)>',
        raw_html, re.IGNORECASE
    ) or re.search(
        r'\b(?:class|id)=["\'][^"\']*\b(?:tldr|summary-block|key-takeaways)\b[^"\']*["\']',
        raw_html, re.IGNORECASE
    ))

    if not has_tldr:
        return [_make_finding(
            rule_id="F-FRSH-008",
            title="Long-form content (>800 words) lacks a visible TL;DR or Key Takeaways summary block",
            severity="low",
            evidence=f"Document contains {len(words)} words but lacks an explicit TL;DR or Key Takeaways section near the top.",
            summary="Add a self-contained 2-3 sentence 'TL;DR' or 'Key Takeaways' bulleted block at the top of long-form articles.",
            priority="low",
            rationale="AI answer engines (Perplexity, ChatGPT) extract summary blocks directly to generate instant answer cards. Providing an explicit summary section maximizes factual retention during AI compression.",
            code_fix=(
                '<div class="key-takeaways">\n'
                '  <h3>Key Takeaways</h3>\n'
                '  <ul>\n'
                '    <li>Fact 1: Key specification or product capability</li>\n'
                '    <li>Fact 2: Measurable performance or benchmark metric</li>\n'
                '  </ul>\n'
                '</div>'
            )
        )]
    return []


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

    # Count buzzwords and weighted substantive tokens
    buzzword_count, buzzword_samples = _count_buzzword_tokens(content_text)
    weighted_subst_score, raw_subst_count = _evaluate_weighted_tokens(content_text)

    # Information Density Score using raw Bucket A substantive token count (Appendix F Section 3)
    density_score = min(100.0, (raw_subst_count / content_token_count) * 100.0)

    # Buzzword ratio
    buzzword_ratio = buzzword_count / content_token_count

    findings = []

    # Include TL;DR summary block check
    findings.extend(check_tldr_summary_block(raw_html, page_url))

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
                f"Substantive factual tokens: {raw_subst_count}; "
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
