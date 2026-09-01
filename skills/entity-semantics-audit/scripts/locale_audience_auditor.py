"""
Subskill 3.4: Locale & Audience Grounding Auditor (Appendix E)
Audits HTML hreflang alternate tags, Schema.org areaServed / inLanguage /
audience properties, and HTML geo-meta tags to ensure AI assistants can
route the correct regional answer to location-aware queries.
Rule IDs: F-ENT-008, F-ENT-009
"""

import re
import json
from html.parser import HTMLParser


# Geo-meta tag names that indicate locale awareness
GEO_META_NAMES = frozenset({
    "geo.position",
    "geo.region",
    "geo.placename",
    "icbm",
    "dc.language",
    "content-language",
    "og:locale",
    "og:locale:alternate",
})


class LocaleParser(HTMLParser):
    """
    Streaming parser that collects:
      - <html lang="..."> attribute
      - <link rel="alternate" hreflang="..." href="..."> tags
      - <meta name="geo.*" ...> and related geo / locale meta tags
      - JSON-LD blocks for offline locale field extraction
    """

    def __init__(self):
        super().__init__()
        self.html_lang       = ""
        self.hreflang_tags   = []   # list of {"hreflang": str, "href": str}
        self.geo_meta        = {}   # name -> content
        self.in_jsonld       = False
        self._current_jsonld = []
        self.jsonld_blocks   = []   # raw strings

    def handle_starttag(self, tag, attrs):
        tag_lower  = tag.lower()
        attr_dict  = {k.lower(): (v or "") for k, v in attrs}

        # ── <html lang="..."> ────────────────────────────────────────────────
        if tag_lower == "html":
            self.html_lang = attr_dict.get("lang", "").strip()

        # ── <link rel="alternate" hreflang="..."> ───────────────────────────
        elif tag_lower == "link":
            rel       = attr_dict.get("rel", "").lower()
            hreflang  = attr_dict.get("hreflang", "").strip()
            href      = attr_dict.get("href", "").strip()
            if "alternate" in rel and hreflang:
                self.hreflang_tags.append({"hreflang": hreflang, "href": href})

        # ── <meta name="geo.*" content="..."> ───────────────────────────────
        elif tag_lower == "meta":
            name    = attr_dict.get("name", "").lower().strip()
            prop    = attr_dict.get("property", "").lower().strip()
            content = attr_dict.get("content", "").strip()
            key     = name or prop
            if key in GEO_META_NAMES and content:
                self.geo_meta[key] = content

        # ── <script type="application/ld+json"> ─────────────────────────────
        elif tag_lower == "script":
            if "application/ld+json" in attr_dict.get("type", "").lower():
                self.in_jsonld       = True
                self._current_jsonld = []

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.in_jsonld:
            self.in_jsonld = False
            self.jsonld_blocks.append("".join(self._current_jsonld).strip())

    def handle_data(self, data):
        if self.in_jsonld:
            self._current_jsonld.append(data)


# ── JSON-LD locale field extraction ─────────────────────────────────────────

def _extract_locale_from_jsonld(blocks):
    """
    Walks all JSON-LD blocks and returns a dict of detected locale fields:
      {
        "area_served":   list[str],
        "in_language":   list[str],
        "audience":      list[str],
        "has_any":       bool        # True if at least one locale field found
      }
    """
    result = {
        "area_served": [],
        "in_language": [],
        "audience":    [],
        "has_any":     False,
    }

    def _walk(obj):
        if isinstance(obj, dict):
            # areaServed
            area = obj.get("areaServed")
            if area is not None:
                result["has_any"] = True
                if isinstance(area, str):
                    result["area_served"].append(area)
                elif isinstance(area, list):
                    result["area_served"].extend(str(a) for a in area)

            # inLanguage
            lang = obj.get("inLanguage")
            if lang is not None:
                result["has_any"] = True
                if isinstance(lang, str):
                    result["in_language"].append(lang)
                elif isinstance(lang, list):
                    result["in_language"].extend(str(l) for l in lang)

            # audience
            aud = obj.get("audience")
            if aud is not None:
                result["has_any"] = True
                if isinstance(aud, dict):
                    result["audience"].append(aud.get("audienceType", repr(aud)))
                elif isinstance(aud, str):
                    result["audience"].append(aud)
                elif isinstance(aud, list):
                    for a in aud:
                        if isinstance(a, dict):
                            result["audience"].append(a.get("audienceType", repr(a)))
                        elif isinstance(a, str):
                            result["audience"].append(a)

            # Recurse into child values
            for val in obj.values():
                if isinstance(val, (dict, list)):
                    _walk(val)

        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    for block in blocks:
        if not block:
            continue
        cleaned = block.strip()
        cleaned = re.sub(r'^\s*<!--', '', cleaned)
        cleaned = re.sub(r'-->\s*$', '', cleaned)
        cleaned = re.sub(r'^\s*(?:/\*\s*<!\[CDATA\[\s*\*/|//\s*<!\[CDATA\[|<!\[CDATA\[)', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'(?:/\*\s*\]\]>\s*\*/|//\s*\]\]>|\]\]>)\s*$', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'^\s*<!--', '', cleaned)
        cleaned = re.sub(r'-->\s*$', '', cleaned).strip()
        if not cleaned:
            continue
        try:
            _walk(json.loads(cleaned))
        except Exception:
            pass

    return result


def check_locale_audience(raw_html, page_url=""):
    """
    Audits locale and audience grounding signals:
      - hreflang alternate link tags (F-ENT-008)
      - Schema.org areaServed / inLanguage / audience (F-ENT-009)
      - Geo-meta tags (geo.position, ICBM, geo.region)

    Args:
        raw_html (str): Raw HTML of the page.
        page_url  (str): Source URL for evidence strings.

    Returns:
        list[dict]: Standardised finding dicts.
    """
    findings = []
    if not raw_html:
        return findings

    # ── Parse HTML ───────────────────────────────────────────────────────────
    parser = LocaleParser()
    try:
        parser.feed(raw_html)
    except Exception:
        pass

    hreflang_tags  = parser.hreflang_tags
    geo_meta       = parser.geo_meta
    html_lang      = parser.html_lang

    locale_schema  = _extract_locale_from_jsonld(parser.jsonld_blocks)

    # Unique language codes declared in hreflang (excluding x-default)
    declared_langs = list({
        tag["hreflang"]
        for tag in hreflang_tags
        if tag["hreflang"].lower() != "x-default"
    })
    is_multi_region_hreflang = len(declared_langs) > 1

    # Multi-language signals from Schema / meta
    multi_lang_schema = len(locale_schema["in_language"]) > 1
    has_multi_region_signal = is_multi_region_hreflang or multi_lang_schema

    # ── F-ENT-008: Multi-language signals present but hreflang is missing ───
    if multi_lang_schema and not hreflang_tags:
        lang_list = ", ".join(locale_schema["in_language"][:4])
        findings.append({
            "id": "F-ENT-008",
            "skill_id": "entity-semantics-audit",
            "title": "Multi-language site missing hreflang alternate link tags",
            "severity": "medium",
            "impact_area": "ai_discoverability",
            "evidence": (
                f"JSON-LD inLanguage declares multiple languages ({lang_list}) indicating "
                f"a multi-language site, but no <link rel=\"alternate\" hreflang=\"...\"> "
                f"tags were found. AI crawlers cannot identify or route to the correct "
                f"language variant."
            ),
            "suggested_action": {
                "summary": (
                    "Add hreflang alternate link tags in <head> for each language/region "
                    "variant, including an x-default fallback."
                ),
                "priority": "medium",
                "rationale": (
                    "Without hreflang, AI assistants and search engines serve incorrect "
                    "language variants to users, or worse, exclude regional pages from "
                    "AI-generated answers entirely. Google's multilingual indexing depends "
                    "on hreflang for correct locale routing."
                ),
                "code_fix_example": (
                    "<link rel=\"alternate\" hreflang=\"en\" href=\"https://acme.com/en/\" />\n"
                    "<link rel=\"alternate\" hreflang=\"de\" href=\"https://acme.com/de/\" />\n"
                    "<link rel=\"alternate\" hreflang=\"fr\" href=\"https://acme.com/fr/\" />\n"
                    "<link rel=\"alternate\" hreflang=\"x-default\" href=\"https://acme.com/\" />"
                ),
            },
        })

    # ── F-ENT-009: Missing locale grounding in Schema.org and geo-meta ───────
    has_any_locale_signal = bool(
        hreflang_tags or
        geo_meta or
        locale_schema["has_any"] or
        html_lang
    )

    if not locale_schema["has_any"] and not geo_meta:
        # Determine evidence detail level
        if hreflang_tags and not locale_schema["area_served"]:
            # hreflang present but not reflected in Schema areaServed
            lang_sample = ", ".join(declared_langs[:4]) or "multiple"
            findings.append({
                "id": "F-ENT-009",
                "skill_id": "entity-semantics-audit",
                "title": "hreflang alternate tags present but Schema.org areaServed property is absent",
                "severity": "low",
                "impact_area": "ai_discoverability",
                "evidence": (
                    f"Found {len(hreflang_tags)} hreflang tag(s) ({lang_sample}) indicating "
                    f"multi-region support, but the Organization / Service JSON-LD block lacks "
                    f"the areaServed property. Structured data does not reflect the site's "
                    f"declared geographic scope."
                ),
                "suggested_action": {
                    "summary": (
                        "Add areaServed to the Organization JSON-LD to align structured data "
                        "with hreflang declarations."
                    ),
                    "priority": "low",
                    "rationale": (
                        "areaServed enables AI assistants to answer regional queries "
                        "('services available in Germany') with precise, schema-sourced "
                        "answers instead of inferring from unstructured page text."
                    ),
                    "code_fix_example": (
                        "{\n"
                        "  \"@type\": \"Organization\",\n"
                        "  \"name\": \"Acme Corp\",\n"
                        "  \"areaServed\": [\"US\", \"GB\", \"DE\", \"FR\", \"AU\"],\n"
                        "  \"inLanguage\": [\"en\", \"de\", \"fr\"]\n"
                        "}"
                    ),
                },
            })
        else:
            # No locale signals at all anywhere
            html_lang_note = f" HTML lang attribute: \"{html_lang}\"." if html_lang else " HTML lang attribute: absent."
            findings.append({
                "id": "F-ENT-009",
                "skill_id": "entity-semantics-audit",
                "title": "Missing locale and audience grounding in structured data and geo-meta tags",
                "severity": "low",
                "impact_area": "ai_discoverability",
                "evidence": (
                    f"No areaServed, inLanguage, or audience properties found in any JSON-LD block. "
                    f"No geo.position, geo.region, or ICBM meta tags detected.{html_lang_note} "
                    f"AI assistants performing location-sensitive queries receive no locale signal."
                ),
                "suggested_action": {
                    "summary": (
                        "Add areaServed and inLanguage to the Organization schema and "
                        "include geo-region meta tags for local relevance signals."
                    ),
                    "priority": "low",
                    "rationale": (
                        "AI assistants performing location-sensitive queries (e.g., 'best CRM "
                        "for UK businesses') use locale schema signals to filter and rank answers. "
                        "Missing locale data reduces visibility in geo-targeted AI responses and "
                        "local intent queries."
                    ),
                    "code_fix_example": (
                        "// In Organization JSON-LD:\n"
                        "{\n"
                        "  \"@type\": \"Organization\",\n"
                        "  \"areaServed\": [\"US\", \"GB\", \"CA\"],\n"
                        "  \"inLanguage\": \"en\",\n"
                        "  \"audience\": {\n"
                        "    \"@type\": \"Audience\",\n"
                        "    \"audienceType\": \"Enterprise B2B\"\n"
                        "  }\n"
                        "}\n\n"
                        "// In <head>:\n"
                        "<meta name=\"geo.region\" content=\"US-CA\" />\n"
                        "<meta name=\"geo.placename\" content=\"San Francisco, CA\" />\n"
                        "<meta name=\"geo.position\" content=\"37.7749;-122.4194\" />"
                    ),
                },
            })

    return findings
