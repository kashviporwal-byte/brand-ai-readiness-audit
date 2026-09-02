"""
Subskill 4.1: Temporal Freshness & Copyright Staleness Checker
Detects missing datePublished/dateModified metadata and stale copyright notices.
Rule IDs: F-FRSH-001, F-FRSH-002, F-FRSH-003
"""

import re
import json
from html.parser import HTMLParser
from datetime import datetime, timezone, timedelta


# ── Constants ─────────────────────────────────────────────────────────────────

# Meta tag name patterns that carry temporal signals (checked case-insensitively)
TEMPORAL_META_NAMES = {
    "article:modified_time",
    "article:published_time",
    "og:updated_time",
    "dc.date",
    "date",
    "last-modified",
    "revised",
}

# JSON-LD fields that carry temporal signals
JSONLD_TEMPORAL_FIELDS = ("dateModified", "datePublished", "uploadDate", "dateCreated")

# ISO 8601 date/datetime patterns accepted as valid
_ISO_DATE_RE = re.compile(
    r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])"
    r"(?:[T ](?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d+)?)?"
    r"(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)?)?$"
)

# Copyright detection patterns
_COPYRIGHT_PATTERNS = [
    # "© 2021", "©2021-2024", "© 2018 – 2023"
    re.compile(r"©\s*(\d{4})(?:\s*[-–—]\s*(\d{4}))?", re.IGNORECASE),
    # "Copyright 2021", "Copyright 2018-2023"
    re.compile(r"copyright\s+(\d{4})(?:\s*[-–—]\s*(\d{4}))?", re.IGNORECASE),
    # "(c) 2021", "(C) 2018-2022"
    re.compile(r"\(c\)\s*(\d{4})(?:\s*[-–—]\s*(\d{4}))?", re.IGNORECASE),
    # "(C) 2021"
    re.compile(r"\(C\)\s*(\d{4})(?:\s*[-–—]\s*(\d{4}))?"),
]

# Minimum word count threshold — pages with fewer visible words are considered
# "thin content" and not worth flagging for missing temporal metadata
_MIN_WORD_COUNT_FOR_TEMPORAL_AUDIT = 30


# ── HTML Parsers ──────────────────────────────────────────────────────────────

class _TemporalMetaParser(HTMLParser):
    """
    Extracts:
    - <meta> tags with temporal property/name attributes
    - <script type="application/ld+json"> blocks
    - <time datetime="..."> attributes
    - <footer> region text (for copyright detection)
    - Visible body text (for word count estimation)
    """

    def __init__(self):
        super().__init__()
        self.meta_timestamps = {}       # {source_name: value_string}
        self.jsonld_blocks = []         # raw JSON strings
        self.time_datetimes = []        # <time datetime="..."> values
        self.footer_text = ""           # text within <footer>
        self.visible_text_words = 0     # approximate visible word count

        self._in_jsonld = False
        self._in_footer = False
        self._skip_tags = {"script", "style", "noscript"}
        self._in_skip = False
        self._current_jsonld_data = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        # JSON-LD blocks
        if tag == "script" and "application/ld+json" in attr_dict.get("type", ""):
            self._in_jsonld = True
            self._current_jsonld_data = []
            return

        # Meta tags
        if tag == "meta":
            name = attr_dict.get("name", attr_dict.get("property", "")).lower().strip()
            content = attr_dict.get("content", "").strip()
            if name in TEMPORAL_META_NAMES and content:
                self.meta_timestamps[name] = content

        # <time> elements
        if tag == "time":
            dt = attr_dict.get("datetime", "").strip()
            if dt:
                self.time_datetimes.append(dt)

        # Footer tracking
        if tag == "footer":
            self._in_footer = True

        # Skip tags
        if tag in self._skip_tags:
            self._in_skip = True

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "script" and self._in_jsonld:
            self._in_jsonld = False
            self.jsonld_blocks.append("".join(self._current_jsonld_data))
            self._current_jsonld_data = []
        if tag == "footer":
            self._in_footer = False
        if tag in self._skip_tags:
            self._in_skip = False

    def handle_data(self, data):
        if self._in_jsonld:
            self._current_jsonld_data.append(data)
            return
        if self._in_skip:
            return
        stripped = data.strip()
        if stripped:
            if self._in_footer:
                self.footer_text += " " + stripped
            self.visible_text_words += len(stripped.split())


# ── Helper Functions ──────────────────────────────────────────────────────────

def _parse_jsonld_blocks(raw_blocks):
    """
    Parse raw JSON-LD blocks and extract temporal field values.
    Returns a dict mapping field_name -> value_string.
    """
    found = {}
    for raw in raw_blocks:
        raw = raw.strip()
        if not raw:
            continue
        # Strip CDATA wrappers
        raw = re.sub(r"^<!\[CDATA\[", "", raw).rstrip("]]>")
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue

        # Handle both single objects and @graph arrays
        items = []
        if isinstance(obj, dict):
            items.append(obj)
            items.extend(obj.get("@graph", []) if isinstance(obj.get("@graph"), list) else [])
        elif isinstance(obj, list):
            items = obj

        for item in items:
            if not isinstance(item, dict):
                continue
            for field in JSONLD_TEMPORAL_FIELDS:
                if field in item and field not in found:
                    val = item[field]
                    if isinstance(val, str) and val.strip():
                        found[field] = val.strip()
    return found


def _validate_iso8601(value, now_utc):
    """
    Returns (is_valid: bool, is_future: bool, parsed_date: datetime or None).
    """
    value = value.strip()
    if not _ISO_DATE_RE.match(value):
        return False, False, None

    # Normalise timezone: replace Z, handle +HH:MM offsets
    clean = value.replace("Z", "+00:00")
    # Replace space-separated datetime with T
    if "T" not in clean and " " in clean:
        clean = clean.replace(" ", "T", 1)

    # Try a sequence of common ISO 8601 formats
    formats_to_try = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    ]
    for fmt in formats_to_try:
        try:
            # Trim the clean string to the format's expected length for safe parsing
            dt = datetime.strptime(clean[:26], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            is_future = dt > now_utc + timedelta(hours=24)
            return True, is_future, dt
        except ValueError:
            continue

    # Valid format pattern but could not parse precisely — assume valid, not future
    return True, False, None


def _extract_copyright_years(text):
    """
    Returns a list of (start_year: int, end_year: int or None) tuples
    from copyright strings found in the given text.
    """
    results = []
    for pattern in _COPYRIGHT_PATTERNS:
        for match in pattern.finditer(text):
            try:
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else None
                if 1990 <= start <= 2100:
                    results.append((start, end))
            except (IndexError, TypeError, ValueError):
                continue
    return results


def _make_finding(rule_id, title, severity, evidence, summary, priority, rationale, code_fix):
    return {
        "id":        rule_id,
        "skill_id":  "freshness-corroboration",
        "title":     title,
        "severity":  severity,
        "impact_area": "ai_discoverability",
        "evidence":  evidence,
        "suggested_action": {
            "summary":          summary,
            "priority":         priority,
            "rationale":        rationale,
            "code_fix_example": code_fix,
        },
    }


# ── Main Public Function ──────────────────────────────────────────────────────

def check_temporal_freshness(raw_html, page_url=""):
    """
    Audits temporal metadata and copyright freshness on the given HTML page.

    Args:
        raw_html (str): The raw HTML of the page.
        page_url (str): URL used in evidence strings.

    Returns:
        list[dict]: Findings conforming to report_schema.json.
    """
    if not raw_html or not raw_html.strip():
        return []

    now_utc = datetime.now(timezone.utc)
    current_year = now_utc.year

    # Parse the HTML
    parser = _TemporalMetaParser()
    try:
        parser.feed(raw_html)
    except Exception:
        return []

    # Bail on thin pages — not worth auditing for temporal metadata
    if parser.visible_text_words < _MIN_WORD_COUNT_FOR_TEMPORAL_AUDIT:
        return []

    # Collect all temporal signals
    jsonld_timestamps = _parse_jsonld_blocks(parser.jsonld_blocks)
    all_timestamps = {}
    all_timestamps.update(parser.meta_timestamps)
    for field, value in jsonld_timestamps.items():
        all_timestamps[f"jsonld:{field}"] = value
    for i, dt_val in enumerate(parser.time_datetimes):
        all_timestamps[f"html:time[{i}]"] = dt_val

    findings = []

    # ── F-FRSH-001: Missing datePublished / dateModified ─────────────────────
    has_modified = (
        "jsonld:dateModified" in all_timestamps
        or "article:modified_time" in all_timestamps
        or "og:updated_time" in all_timestamps
        or "last-modified" in all_timestamps
        or "revised" in all_timestamps
    )
    has_published = (
        "jsonld:datePublished" in all_timestamps
        or "article:published_time" in all_timestamps
        or "jsonld:dateCreated" in all_timestamps
        or "date" in all_timestamps
        or "dc.date" in all_timestamps
    )

    if not has_modified and not has_published:
        findings.append(_make_finding(
            rule_id="F-FRSH-001",
            title="Missing datePublished / dateModified temporal metadata",
            severity="high",
            evidence=(
                f"No machine-readable publication or modification date found on {page_url or 'this page'}. "
                "Checked JSON-LD (datePublished, dateModified), Open Graph meta tags "
                "(article:published_time, article:modified_time), Dublin Core (DC.date), "
                "and HTML <time datetime> elements. AI retrieval systems discount "
                "undated content and may omit it from recency-sensitive queries."
            ),
            summary=(
                "Add datePublished and dateModified timestamps in JSON-LD structured data "
                "and Open Graph meta tags."
            ),
            priority="high",
            rationale=(
                "AI assistants (Perplexity, ChatGPT Browse, Bing Copilot) apply temporal "
                "decay weighting. Undated pages are ranked lower in recency-filtered queries "
                "and may be excluded from 'recent news' or 'latest updates' answer sets."
            ),
            code_fix=(
                '<!-- In <head>: -->\n'
                '<meta property="article:published_time" content="2025-01-15T09:00:00Z" />\n'
                '<meta property="article:modified_time" content="2025-09-01T12:00:00Z" />\n\n'
                '<!-- JSON-LD: -->\n'
                '<script type="application/ld+json">\n'
                '{\n'
                '  "@context": "https://schema.org",\n'
                '  "@type": "WebPage",\n'
                '  "datePublished": "2025-01-15T09:00:00Z",\n'
                '  "dateModified": "2025-09-01T12:00:00Z"\n'
                '}\n'
                '</script>'
            ),
        ))
    elif not has_modified:
        findings.append(_make_finding(
            rule_id="F-FRSH-001",
            title="Missing dateModified — page has publication date but no modification timestamp",
            severity="medium",
            evidence=(
                f"Page has a publication date signal but no dateModified or article:modified_time. "
                f"Publication date sources detected: {list(k for k in all_timestamps if 'publish' in k.lower() or 'date' in k.lower())[:3]}. "
                "Without a modification timestamp, AI systems cannot determine if stale content has been updated."
            ),
            summary="Add a dateModified timestamp to indicate content freshness to AI crawlers.",
            priority="medium",
            rationale=(
                "dateModified is the primary freshness signal used by AI and search engine crawlers. "
                "Without it, content that is regularly updated appears perpetually stale."
            ),
            code_fix=(
                '<meta property="article:modified_time" content="2025-09-01T12:00:00Z" />\n\n'
                '<!-- Or in JSON-LD: -->\n'
                '"dateModified": "2025-09-01T12:00:00Z"'
            ),
        ))

    # ── F-FRSH-003: Malformed or Future-Dated Timestamps ─────────────────────
    for source, value in all_timestamps.items():
        is_valid, is_future, _ = _validate_iso8601(value, now_utc)
        if not is_valid:
            findings.append(_make_finding(
                rule_id="F-FRSH-003",
                title=f"Malformed temporal timestamp in {source}",
                severity="medium",
                evidence=(
                    f"Timestamp value '{value}' in '{source}' does not conform to ISO 8601 format. "
                    "AI parsers expect YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ. "
                    "Human-readable formats like 'June 15, 2025' are not machine-parseable."
                ),
                summary=(
                    f"Correct the timestamp in '{source}' to ISO 8601 format "
                    "(e.g., 2025-06-15T14:30:00Z)."
                ),
                priority="medium",
                rationale=(
                    "Non-ISO timestamps cannot be reliably parsed by automated crawlers, "
                    "causing the date signal to be silently ignored, as if it were missing."
                ),
                code_fix=(
                    f'<!-- Replace: {value} -->\n'
                    f'<!-- With: 2025-09-01T12:00:00Z (or YYYY-MM-DD date-only form) -->'
                ),
            ))
        elif is_future:
            findings.append(_make_finding(
                rule_id="F-FRSH-003",
                title=f"Future-dated timestamp detected in {source}",
                severity="medium",
                evidence=(
                    f"Timestamp '{value}' in '{source}' is dated in the future "
                    f"(current UTC time: {now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}). "
                    "Future dates confuse AI crawlers and can cause content to be "
                    "incorrectly categorised or excluded from current-date result sets."
                ),
                summary=f"Correct the future-dated timestamp in '{source}' to a valid past or present date.",
                priority="medium",
                rationale=(
                    "Future-dated content may be treated as pre-published or erroneous by "
                    "AI temporal ranking systems, leading to unexpected exclusion from search results."
                ),
                code_fix=(
                    f'<!-- Replace: {value} -->\n'
                    f'<!-- With current UTC time: {now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")} -->'
                ),
            ))

    # ── F-FRSH-002: Stale Copyright Notice ───────────────────────────────────
    # Scan footer text + a wider text buffer from visible page text
    copyright_search_text = parser.footer_text
    if not copyright_search_text:
        # Fallback: search the last 2000 characters of raw HTML for copyright patterns
        copyright_search_text = raw_html[-2000:]

    copyright_entries = _extract_copyright_years(copyright_search_text)

    for start_year, end_year in copyright_entries:
        effective_year = end_year if end_year else start_year
        gap = current_year - effective_year

        if gap > 2:
            severity = "medium"  # Spec 4.1: Medium when > 2 years out of date
            year_display = f"{start_year}–{end_year}" if end_year else str(start_year)
            findings.append(_make_finding(
                rule_id="F-FRSH-002",
                title=f"Stale copyright notice: © {year_display} is {gap} year(s) out of date",
                severity=severity,
                evidence=(
                    f"Copyright notice '© {year_display}' detected on page. "
                    f"Current year: {current_year}. Gap: {gap} year(s). "
                    "Stale copyright notices signal site neglect to AI systems and users, "
                    "reducing perceived content authority and freshness."
                ),
                summary=(
                    f"Update the copyright year from '{year_display}' to '{current_year}', "
                    "or make it dynamic using JavaScript."
                ),
                priority=severity,
                rationale=(
                    "Stale copyright years are a visible freshness decay signal. "
                    "AI assistants performing entity trustworthiness assessments may "
                    "interpret outdated copyright notices as evidence of abandoned or "
                    "unmaintained content."
                ),
                code_fix=(
                    f'<!-- BEFORE (stale): -->\n'
                    f'<footer>© {year_display} AcmeCorp. All rights reserved.</footer>\n\n'
                    f'<!-- AFTER (dynamic): -->\n'
                    f'<footer>© <span id="cr-year"></span> AcmeCorp. All rights reserved.</footer>\n'
                    f'<script>document.getElementById("cr-year").textContent = new Date().getFullYear();</script>'
                ),
            ))

    return findings
