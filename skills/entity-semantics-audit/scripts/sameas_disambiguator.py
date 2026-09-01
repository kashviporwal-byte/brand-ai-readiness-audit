"""
Subskill 3.2: Entity Disambiguation via sameAs Links Auditor
Detects missing or insufficient outbound authority links that ground the brand
entity in universal Knowledge Graphs (Wikidata, Wikipedia, Crunchbase, etc.).
Rule IDs: F-ENT-004, F-ENT-005
"""

import re
import json
from html.parser import HTMLParser


# Tier 1: Primary knowledge graph anchors — the gold standard for AI entity resolution
AUTHORITY_KG_DOMAINS = {
    "wikidata.org":       "Wikidata",
    "wikipedia.org":      "Wikipedia",
    "dbpedia.org":        "DBpedia",
}

# Tier 2: Business registry / directory sources — trusted but not primary KG anchors
AUTHORITY_DIRECTORY_DOMAINS = {
    "crunchbase.com":     "Crunchbase",
    "bloomberg.com":      "Bloomberg",
    "sec.gov":            "SEC EDGAR",
    "opencorporates.com": "OpenCorporates",
    "dnb.com":            "Dun & Bradstreet",
    "companieshouse.gov": "Companies House (UK)",
    "pitchbook.com":      "PitchBook",
}

# Tier 3: Social / community profiles — useful but insufficient alone for disambiguation
SOCIAL_DOMAINS = {
    "linkedin.com":       "LinkedIn",
    "twitter.com":        "Twitter/X",
    "x.com":              "Twitter/X",
    "facebook.com":       "Facebook",
    "instagram.com":      "Instagram",
    "youtube.com":        "YouTube",
    "github.com":         "GitHub",
    "glassdoor.com":      "Glassdoor",
    "g2.com":             "G2",
    "trustpilot.com":     "Trustpilot",
    "producthunt.com":    "Product Hunt",
    "ycombinator.com":    "Y Combinator",
}


class SameAsExtractor(HTMLParser):
    """
    Extracts sameAs values from JSON-LD blocks and scans outbound
    hyperlinks for authority domain signals.
    """

    def __init__(self):
        super().__init__()
        self.in_jsonld = False
        self._current_data = []
        self.sameas_from_jsonld = []   # Links found inside sameAs arrays
        self.all_hrefs = []            # All href values from <a> and <link> tags

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag_lower == "script":
            if "application/ld+json" in attr_dict.get("type", "").lower():
                self.in_jsonld = True
                self._current_data = []

        elif tag_lower in ("a", "link"):
            href = attr_dict.get("href", "")
            if href and href.startswith("http"):
                self.all_hrefs.append(href)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.in_jsonld:
            self.in_jsonld = False
            block = "".join(self._current_data).strip()
            if block:
                try:
                    data = json.loads(block)
                    self._recurse_sameas(data)
                except Exception:
                    pass
            self._current_data = []

    def handle_data(self, data):
        if self.in_jsonld:
            self._current_data.append(data)

    def _recurse_sameas(self, obj):
        """Recursively walks JSON-LD structure to find all sameAs values."""
        if isinstance(obj, dict):
            same_as = obj.get("sameAs", [])
            if isinstance(same_as, str) and same_as.startswith("http"):
                self.sameas_from_jsonld.append(same_as)
            elif isinstance(same_as, list):
                for s in same_as:
                    if isinstance(s, str) and s.startswith("http"):
                        self.sameas_from_jsonld.append(s)
            # Walk @graph or nested schemas
            for val in obj.values():
                if isinstance(val, (dict, list)):
                    self._recurse_sameas(val)
        elif isinstance(obj, list):
            for item in obj:
                self._recurse_sameas(item)


def _classify_url(url):
    """
    Classifies a URL into one of:
      ('kg',        label)   — Wikidata / Wikipedia / DBpedia
      ('directory', label)   — Crunchbase / SEC / Bloomberg etc.
      ('social',    label)   — LinkedIn / GitHub / Twitter etc.
      ('other',     url)     — Unrecognised
    """
    url_lower = url.lower()
    for domain, label in AUTHORITY_KG_DOMAINS.items():
        if domain in url_lower:
            return "kg", label
    for domain, label in AUTHORITY_DIRECTORY_DOMAINS.items():
        if domain in url_lower:
            return "directory", label
    for domain, label in SOCIAL_DOMAINS.items():
        if domain in url_lower:
            return "social", label
    return "other", url


def _summarise_links(links):
    """Returns a human-readable summary string for up to 4 links."""
    summary = []
    for link in links[:4]:
        _, label = _classify_url(link)
        summary.append(label)
    suffix = f" (+{len(links) - 4} more)" if len(links) > 4 else ""
    return ", ".join(summary) + suffix


def check_sameas_disambiguation(raw_html, page_url=""):
    """
    Audits entity disambiguation signals by inspecting sameAs arrays in
    JSON-LD structured data and outbound hyperlinks to authority domains.

    Args:
        raw_html (str): Raw HTML of the page.
        page_url  (str): Source URL for evidence strings.

    Returns:
        list[dict]: Standardised finding dicts.
    """
    findings = []
    if not raw_html:
        return findings

    # ── Parse HTML for sameAs and authority outbound links ──────────────────
    extractor = SameAsExtractor()
    try:
        extractor.feed(raw_html)
    except Exception:
        pass

    # Deduplicate
    jsonld_sameas = list(dict.fromkeys(extractor.sameas_from_jsonld))
    all_hrefs     = list(dict.fromkeys(extractor.all_hrefs))

    # Classify each sameAs link
    kg_links        = []
    directory_links = []
    social_links    = []
    other_links     = []

    for link in jsonld_sameas:
        kind, label = _classify_url(link)
        if kind == "kg":
            kg_links.append(label)
        elif kind == "directory":
            directory_links.append(label)
        elif kind == "social":
            social_links.append(label)
        else:
            other_links.append(link)

    has_kg_anchor = bool(kg_links)
    has_any_sameas = bool(jsonld_sameas)

    # Detect authority outbound links in page body (not in sameAs)
    page_authority_labels = []
    for href in all_hrefs:
        kind, label = _classify_url(href)
        if kind in ("kg", "directory"):
            if label not in page_authority_labels:
                page_authority_labels.append(label)

    # ── F-ENT-004: No sameAs links whatsoever ───────────────────────────────
    if not has_any_sameas:
        if page_authority_labels:
            # Authority links detected in page body — advise promoting them to sameAs
            evidence = (
                f"No sameAs property found in any JSON-LD block. However, outbound "
                f"hyperlinks to authority sources ({', '.join(page_authority_labels[:3])}) "
                f"exist in the page body and should be promoted to the Organization sameAs array."
            )
            severity = "medium"
            rule_id  = "F-ENT-005"
            title    = "Brand entity links to authority sources in body but lacks sameAs in structured data"
        else:
            evidence = (
                "No sameAs property found in any JSON-LD block. No outbound hyperlinks "
                "to authoritative knowledge graph sources (Wikidata, Wikipedia, Crunchbase) "
                "detected anywhere on the page."
            )
            severity = "high"
            rule_id  = "F-ENT-004"
            title    = "Brand entity completely lacks sameAs knowledge graph disambiguation links"

        findings.append({
            "id": rule_id,
            "skill_id": "entity-semantics-audit",
            "title": title,
            "severity": severity,
            "impact_area": "ai_discoverability",
            "evidence": evidence,
            "suggested_action": {
                "summary": (
                    "Add a sameAs array to the Organization JSON-LD populated with "
                    "Wikidata, Wikipedia, and Crunchbase profile URLs."
                ),
                "priority": severity,
                "rationale": (
                    "Without sameAs grounding, AI language models (ChatGPT, Claude, "
                    "Perplexity) cannot reliably distinguish this brand from identically-named "
                    "entities. This is the primary cause of brand hallucination, misattribution, "
                    "and factual errors in AI-generated answers about the brand."
                ),
                "code_fix_example": (
                    "{\n"
                    "  \"@type\": \"Organization\",\n"
                    "  \"name\": \"Acme Corp\",\n"
                    "  \"sameAs\": [\n"
                    "    \"https://www.wikidata.org/wiki/Q12345\",\n"
                    "    \"https://en.wikipedia.org/wiki/Acme_Corp\",\n"
                    "    \"https://www.crunchbase.com/organization/acme-corp\",\n"
                    "    \"https://www.linkedin.com/company/acme-corp\",\n"
                    "    \"https://github.com/acme-corp\"\n"
                    "  ]\n"
                    "}"
                ),
            },
        })

        return findings

    # ── F-ENT-005: Has sameAs but no Tier-1 KG anchors ──────────────────────
    if not has_kg_anchor:
        all_present_labels = (directory_links + social_links)[:5]
        summary_str = ", ".join(all_present_labels) if all_present_labels else "unrecognised sources"
        findings.append({
            "id": "F-ENT-005",
            "skill_id": "entity-semantics-audit",
            "title": "sameAs links present but missing primary knowledge graph anchors (Wikidata / Wikipedia)",
            "severity": "medium",
            "impact_area": "ai_discoverability",
            "evidence": (
                f"Found {len(jsonld_sameas)} sameAs link(s) referencing: {summary_str}. "
                f"None reference Wikidata or Wikipedia — the Tier-1 entity resolution sources "
                f"used by AI knowledge graphs to disambiguate brand identities."
            ),
            "suggested_action": {
                "summary": (
                    "Register the brand on Wikidata and/or Wikipedia, then add the "
                    "authoritative entity URL(s) to the sameAs array."
                ),
                "priority": "medium",
                "rationale": (
                    "AI assistants (ChatGPT, Perplexity, Claude) use Wikidata Q-items "
                    "and Wikipedia articles as ground-truth entity anchors during knowledge "
                    "graph lookup. Social and directory profile links alone cannot prevent "
                    "brand name collisions with similarly-named entities."
                ),
                "code_fix_example": (
                    "// Add Wikidata and Wikipedia to existing sameAs array:\n"
                    "\"sameAs\": [\n"
                    "  \"https://www.wikidata.org/wiki/Q12345\",    // Tier-1 KG anchor\n"
                    "  \"https://en.wikipedia.org/wiki/Acme_Corp\", // Tier-1 KG anchor\n"
                    "  // ... keep existing social / directory links below ...\n"
                    "]"
                ),
            },
        })

    return findings
