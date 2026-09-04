"""
Subskill 3.1: Schema.org JSON-LD Structured Data Auditor
Detects missing, syntactically invalid, or incomplete Schema.org JSON-LD markup.
Rule IDs: F-ENT-001, F-ENT-002, F-ENT-003
"""

import re
import json
from html.parser import HTMLParser


# Core entity types that must appear on brand/product pages
CORE_ENTITY_TYPES = {
    "Organization", "Corporation", "LocalBusiness", "Brand",
    "Product", "Service", "SoftwareApplication", "WebApplication",
}

# Informational content types (good to have but not the primary entity)
CONTENT_TYPES = {
    "FAQPage", "Article", "NewsArticle", "BlogPosting",
    "BreadcrumbList", "WebPage", "WebSite",
}

# Critical fields required per entity type (lowercase for comparison)
CRITICAL_FIELDS_BY_TYPE = {
    "Organization":        {"name", "description", "url", "logo"},
    "Corporation":         {"name", "description", "url", "logo"},
    "LocalBusiness":       {"name", "description", "url", "address"},
    "Brand":               {"name", "description", "url"},
    "Product":             {"name", "description", "offers"},
    "Service":             {"name", "description", "provider"},
    "SoftwareApplication": {"name", "description", "operatingSystem"},
    "WebApplication":      {"name", "description", "applicationCategory"},
}

# Default fallback for unmapped entity types
DEFAULT_CRITICAL_FIELDS = {"name", "description"}


class JSONLDExtractor(HTMLParser):
    """
    Streaming parser that extracts all <script type="application/ld+json"> blocks
    from raw HTML without loading any third-party library.
    """

    def __init__(self):
        super().__init__()
        self.in_jsonld = False
        self._current_data = []
        self.raw_blocks = []   # Unparsed raw JSON strings

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script":
            attr_dict = {k.lower(): (v or "").lower() for k, v in attrs}
            if "application/ld+json" in attr_dict.get("type", ""):
                self.in_jsonld = True
                self._current_data = []

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.in_jsonld:
            self.in_jsonld = False
            self.raw_blocks.append("".join(self._current_data))
            self._current_data = []

    def handle_data(self, data):
        if self.in_jsonld:
            self._current_data.append(data)


def _clean_type_string(t):
    """Strips namespace prefixes, schemas URLs, and URI fragments from a @type string."""
    if not isinstance(t, str):
        return ""
    t = t.strip()
    if "/" in t:
        t = t.rsplit("/", 1)[-1]
    if "#" in t:
        t = t.rsplit("#", 1)[-1]
    if ":" in t and not t.startswith("http"):
        t = t.split(":", 1)[-1]
    return t.strip()


def _normalize_type(type_val):
    """Normalises @type into a flat list of clean type name strings regardless of input shape or URI prefix."""
    raw = [type_val] if isinstance(type_val, str) else type_val if isinstance(type_val, list) else []
    cleaned_types = []
    for t in raw:
        if isinstance(t, str):
            clean = _clean_type_string(t)
            if clean:
                cleaned_types.append(clean)
    return cleaned_types


def _clean_jsonld_raw_block(raw_block):
    """
    Strips HTML comments (<!-- ... -->), CDATA wrappers (/* <![CDATA[ */, // <![CDATA[),
    and leading/trailing whitespace/bom before JSON parsing.
    """
    if not isinstance(raw_block, str):
        return ""
    cleaned = raw_block.strip()
    # Strip HTML comment start <!-- and end -->
    cleaned = re.sub(r'^\s*<!--', '', cleaned)
    cleaned = re.sub(r'-->\s*$', '', cleaned)
    # Strip CDATA wrappers /* <![CDATA[ */ or // <![CDATA[ or <![CDATA[
    cleaned = re.sub(r'^\s*(?:/\*\s*<!\[CDATA\[\s*\*/|//\s*<!\[CDATA\[|<!\[CDATA\[)', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'(?:/\*\s*\]\]>\s*\*/|//\s*\]\]>|\]\]>)\s*$', '', cleaned, flags=re.IGNORECASE)
    # Trailing/leading comment markers cleanup
    cleaned = re.sub(r'^\s*<!--', '', cleaned)
    cleaned = re.sub(r'-->\s*$', '', cleaned)
    return cleaned.strip()


def _flatten_schemas(data):
    """
    Recursively flattens @graph wrappers and top-level arrays into a
    flat list of individual schema dicts.
    """
    schemas = []
    if isinstance(data, dict):
        if "@graph" in data:
            items = data["@graph"]
            schemas.extend(_flatten_schemas(items))
        else:
            schemas.append(data)
    elif isinstance(data, list):
        for item in data:
            schemas.extend(_flatten_schemas(item))
    return schemas


def check_jsonld_schema(raw_html, page_url=""):
    """
    Audits Schema.org JSON-LD blocks for:
      - Presence (F-ENT-001)
      - Field completeness (F-ENT-002)
      - JSON syntax validity (F-ENT-003)

    Args:
        raw_html (str): Raw HTML of the page.
        page_url  (str): Source URL for evidence strings.

    Returns:
        list[dict]: Standardised finding dicts conforming to report_schema.json.
    """
    findings = []
    if not raw_html:
        return findings

    # ── F-ENT-010: Check FAQ / HowTo schema gap for Q&A content ──────────────
    # Runs unconditionally, before the zero-schema early return below, so it fires
    # on pages with ZERO structured data (the common case) as well as pages with
    # partial schema. Previously this call sat after the early return and was
    # unreachable for any page lacking an entity schema.
    findings.extend(check_faq_howto_schema_gap(raw_html, page_url))

    # ── Step 1: Extract all JSON-LD blocks ──────────────────────────────────
    extractor = JSONLDExtractor()
    try:
        extractor.feed(raw_html)
    except Exception:
        pass

    parsed_schemas = []
    invalid_blocks = []

    for raw_block in extractor.raw_blocks:
        raw_block = raw_block.strip()
        if not raw_block:
            continue
        cleaned_block = _clean_jsonld_raw_block(raw_block)
        if not cleaned_block:
            continue
        try:
            data = json.loads(cleaned_block)
            parsed_schemas.extend(_flatten_schemas(data))
        except (json.JSONDecodeError, ValueError):
            # Keep a preview for evidence
            invalid_blocks.append(raw_block[:100].replace("\n", " "))

    # ── F-ENT-003: Invalid / unparseable JSON-LD ────────────────────────────
    if invalid_blocks:
        preview = invalid_blocks[0]
        findings.append({
            "id": "F-ENT-003",
            "skill_id": "entity-semantics-audit",
            "title": "Malformed JSON-LD blocks cause silent structured data failures",
            "severity": "high",
            "impact_area": "ai_discoverability",
            "evidence": (
                f"Found {len(invalid_blocks)} <script type=\"application/ld+json\"> "
                f"block(s) that fail JSON parsing and are silently ignored by all crawlers. "
                f"Preview of first invalid block: \"{preview}...\""
            ),
            "suggested_action": {
                "summary": "Validate and fix JSON syntax errors in all structured data blocks.",
                "priority": "high",
                "rationale": (
                    "Malformed JSON-LD is silently discarded by Google, Bing, and AI knowledge "
                    "graph extractors. The structured data provides zero benefit despite being "
                    "present in the markup."
                ),
                "code_fix_example": (
                    "// Validate at https://validator.schema.org/\n"
                    "<script type=\"application/ld+json\">\n"
                    "{\n"
                    "  \"@context\": \"https://schema.org\",\n"
                    "  \"@type\": \"Organization\",\n"
                    "  \"name\": \"Acme Corp\"\n"
                    "}\n"
                    "</script>"
                ),
            },
        })

    # Classify parsed schemas into entity vs. content types
    entity_schemas = []   # [(types_list, schema_dict)]
    found_type_names = []

    for schema in parsed_schemas:
        if not isinstance(schema, dict):
            continue
        types = _normalize_type(schema.get("@type", ""))
        found_type_names.extend(types)
        if any(t in CORE_ENTITY_TYPES for t in types):
            entity_schemas.append((types, schema))

    # ── F-ENT-001: No core entity schema present ────────────────────────────
    if not entity_schemas:
        total_blocks = len(parsed_schemas) + len(invalid_blocks)
        if total_blocks == 0:
            evidence = (
                "No <script type=\"application/ld+json\"> blocks found on the page. "
                "The page has zero structured data markup."
            )
        else:
            unique_types = ", ".join(sorted(set(found_type_names))) or "none"
            evidence = (
                f"Found {len(parsed_schemas)} valid JSON-LD block(s) but none declare a "
                f"core entity type (Organization, Corporation, Product, Service, "
                f"SoftwareApplication). Detected @types: [{unique_types}]."
            )
        findings.append({
            "id": "F-ENT-001",
            "skill_id": "entity-semantics-audit",
            "title": "Missing core Schema.org entity markup (Organization or Product)",
            "severity": "high",
            "impact_area": "ai_discoverability",
            "evidence": evidence,
            "suggested_action": {
                "summary": (
                    "Add a Schema.org Organization or Product JSON-LD block to the "
                    "homepage and all primary landing pages."
                ),
                "priority": "high",
                "rationale": (
                    "Without a core entity schema, AI knowledge graph extractors cannot "
                    "reliably associate the page with the brand entity, leading to "
                    "hallucinated or missing brand facts in AI-generated answers. "
                    "This is the single highest-impact structured data defect."
                ),
                "code_fix_example": (
                    "<script type=\"application/ld+json\">\n"
                    "{\n"
                    "  \"@context\": \"https://schema.org\",\n"
                    "  \"@type\": \"Organization\",\n"
                    "  \"name\": \"Acme Corp\",\n"
                    "  \"description\": \"Acme Corp provides automated enterprise "
                    "workflow orchestration for Fortune 500 teams.\",\n"
                    "  \"url\": \"https://acme.com\",\n"
                    "  \"logo\": \"https://acme.com/logo.png\",\n"
                    "  \"sameAs\": [\n"
                    "    \"https://www.wikidata.org/wiki/Q12345\",\n"
                    "    \"https://en.wikipedia.org/wiki/Acme_Corp\"\n"
                    "  ]\n"
                    "}\n"
                    "</script>"
                ),
            },
        })
        # No entity schemas to inspect for field completeness
        return findings

    # ── F-ENT-002: Entity schemas missing critical fields ───────────────────
    incomplete_reports = []

    for types, schema in entity_schemas:
        schema_keys_lower = {k.lower() for k in schema.keys()}
        primary_type = next((t for t in types if t in CRITICAL_FIELDS_BY_TYPE), types[0] if types else "")
        required_fields = CRITICAL_FIELDS_BY_TYPE.get(primary_type, DEFAULT_CRITICAL_FIELDS)
        missing = sorted(f for f in required_fields if f.lower() not in schema_keys_lower)

        if missing:
            incomplete_reports.append((primary_type, missing))

    if incomplete_reports:
        detail_parts = [
            f"{stype} missing [{', '.join(fields)}]"
            for stype, fields in incomplete_reports
        ]
        findings.append({
            "id": "F-ENT-002",
            "skill_id": "entity-semantics-audit",
            "title": "Schema.org entity blocks present but missing critical required fields",
            "severity": "medium",
            "impact_area": "ai_discoverability",
            "evidence": (
                f"Inspected {len(entity_schemas)} core entity schema(s). "
                f"Incomplete schemas: {'; '.join(detail_parts)}."
            ),
            "suggested_action": {
                "summary": (
                    "Populate all required Schema.org fields: description, logo, url, "
                    "and offers (for Product/Service types)."
                ),
                "priority": "medium",
                "rationale": (
                    "Incomplete schemas leave AI knowledge graph gaps. Models that find "
                    "an Organization @type but no description or logo fall back to "
                    "scraping unstructured page text, significantly increasing the risk "
                    "of hallucinated or inaccurate brand facts in AI answers."
                ),
                "code_fix_example": (
                    "{\n"
                    "  \"@type\": \"Organization\",\n"
                    "  \"name\": \"Acme Corp\",\n"
                    "  \"description\": \"Acme Corp automates enterprise workflows "
                    "for Fortune 500 companies.\",\n"
                    "  \"url\": \"https://acme.com\",\n"
                    "  \"logo\": {\n"
                    "    \"@type\": \"ImageObject\",\n"
                    "    \"url\": \"https://acme.com/logo.png\",\n"
                    "    \"width\": 600,\n"
                    "    \"height\": 60\n"
                    "  },\n"
                    "  \"offers\": {\n"
                    "    \"@type\": \"Offer\",\n"
                    "    \"priceCurrency\": \"USD\",\n"
                    "    \"url\": \"https://acme.com/pricing\"\n"
                    "  }\n"
                    "}"
                ),
            },
        })

    return findings


def check_faq_howto_schema_gap(raw_html, page_url=""):
    """
    F-ENT-010: Missing FAQPage / HowTo / Speakable Schema markup despite presence of Q&A content.
    """
    if not raw_html:
        return []

    question_headings = re.findall(
        r'<h[23]\b[^>]*>(?:\s*<[^>]+>)*\s*([^<]*?\b(?:what|how|why|when|where|who|can|does|is|are)\b[^<]*?\?)\s*(?:<[^>]+>\s*)*</h[23]>',
        raw_html, re.IGNORECASE
    )

    if len(question_headings) < 2:
        return []

    extractor = JSONLDExtractor()
    try:
        extractor.feed(raw_html)
    except Exception:
        pass

    has_faq_howto = False
    for raw_block in extractor.raw_blocks:
        cleaned = _clean_jsonld_raw_block(raw_block)
        if "FAQPage" in cleaned or "HowTo" in cleaned or "Speakable" in cleaned or "Question" in cleaned:
            has_faq_howto = True
            break

    if not has_faq_howto:
        sample_q = question_headings[0].strip()
        return [{
            "id": "F-ENT-010",
            "skill_id": "entity-semantics-audit",
            "title": f"FAQ/Q&A content present ({len(question_headings)} questions detected) but lacks FAQPage Schema.org markup",
            "severity": "medium",
            "impact_area": "ai_discoverability",
            "evidence": f"Found {len(question_headings)} question headings on page (e.g. '{sample_q}'), but no FAQPage or HowTo JSON-LD schema block was detected.",
            "suggested_action": {
                "summary": "Wrap Q&A section content in a Schema.org FAQPage or HowTo JSON-LD block.",
                "priority": "medium",
                "rationale": "AI answer engines (ChatGPT, Claude, Perplexity) directly parse FAQPage JSON-LD to generate instant direct-answer citations. Unstructured Q&A text carries higher extraction risk.",
                "code_fix_example": (
                    '<script type="application/ld+json">\n'
                    '{\n'
                    '  "@context": "https://schema.org",\n'
                    '  "@type": "FAQPage",\n'
                    '  "mainEntity": [{\n'
                    '    "@type": "Question",\n'
                    '    "name": "' + sample_q.replace('"', '\\"') + '",\n'
                    '    "acceptedAnswer": {\n'
                    '      "@type": "Answer",\n'
                    '      "text": "Provide clear, factual 2-sentence answer here."\n'
                    '    }\n'
                    '  }]\n'
                    '}\n'
                    '</script>'
                )
            }
        }]

    return []

