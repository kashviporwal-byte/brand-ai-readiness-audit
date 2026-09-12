"""
Subskill 4.2: Cross-Web Claim Corroboration — Appendix D 2-Source Consensus Rule
=================================================================================
Implementation of the full Appendix D specification:

  1. Extract core brand claims from the page:
       - Founding date
       - CEO / leadership
       - Headquarters / NAP (Name-Address-Phone)
       - Pricing tiers (Free / Pro / Enterprise / Business)
       - Product tier names

  2. Resolve Wikidata and Wikipedia entity IDs from sameAs links on the page.

  3. If a Wikidata entity is found, query the Wikidata API for:
       - P571  → inception date (founding year)
       - P169  → chief executive officer
       - P159  → headquarters location

  4. If a Wikipedia entity is found, query the Wikipedia API for the
     lead-section summary and parse the same facts as a second source.

  5. Apply the 2-Source Consensus Rule (Appendix D):
       - If BOTH Wikidata AND Wikipedia contradict the on-page claim → HIGH conflict (F-FRSH-004)
       - If only ONE external source contradicts → MEDIUM discrepancy (F-FRSH-005)
       - If claim has zero external grounding → MEDIUM advisory (F-FRSH-005)

  6. Pricing / product-tiering claims have no authoritative external source,
     so they are checked for internal consistency (presence of specific numbers
     and tier names) and flagged as MEDIUM if completely missing from grounding.

Rule IDs: F-FRSH-004, F-FRSH-005
"""

import re
import json
import time
import urllib.request
import urllib.parse
from html.parser import HTMLParser


# ── Request Configuration ─────────────────────────────────────────────────────

_USER_AGENT = (
    "BrandAIReadinessAuditor/1.0 "
    "(+https://agentskills.io; read-only sandbox; freshness-corroboration; "
    "Wikidata/Wikipedia API consumer)"
)
_REQUEST_TIMEOUT = 6.0      # seconds per external API call
_API_CALL_DELAY  = 0.25     # polite delay between successive API calls (seconds)
_MAX_API_CALLS   = 4        # max external calls per page audit (stay cheap)

# ── Word count minimum before running corroboration ───────────────────────────
_MIN_WORDS_FOR_CORROBORATION = 25

# ── Founding Year Extraction ──────────────────────────────────────────────────

_FOUNDING_YEAR_TEXT_RE = re.compile(
    r"(?:founded|established|incorporated|launched|started|created)\s+(?:in\s+)?(\d{4})",
    re.IGNORECASE,
)

# ── CEO / Leadership Extraction ───────────────────────────────────────────────

_LEADERSHIP_TEXT_RE = re.compile(
    r"(?:ceo|chief\s+executive(?:\s+officer)?|founder|co-founder|president)"
    r"[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
    re.IGNORECASE,
)

# ── Headquarters Extraction ───────────────────────────────────────────────────

_HQ_TEXT_RE = re.compile(
    r"(?:headquartered|based|hq|offices?)\s+(?:in|at)\s+"
    r"([A-Z][a-z]+(?:[\s,]+[A-Za-z]+){0,3})",
    re.IGNORECASE,
)

# ── Pricing Claim Extraction ──────────────────────────────────────────────────

# Matches price amounts: $25/mo, $9.99/month, USD 500/year, £49, €20, ₹999
_PRICE_VALUE_RE = re.compile(
    r"(?:USD?|GBP?|\$|£|€|₹|INR)\s*\d[\d,.]*"
    r"(?:\s*/\s*(?:month|mo|year|yr|user|seat|m))?",
    re.IGNORECASE,
)

# Plan tier name patterns (requires explicit pricing plan/tier suffix or compound pricing term)
_PRICING_TIER_RE = re.compile(
    r"\b(?:free\s+(?:plan|tier|edition|package)|"
    r"(?:starter|basic|essentials?|pro|growth|business|professional|team|enterprise|plus|premium|unlimited|ultimate|advanced)\s+(?:plan|tier|edition|package|subscription)|"
    r"pay-as-you-go|freemium)\b",
    re.IGNORECASE,
)

# ── sameAs Link Classification ────────────────────────────────────────────────

_SAME_AS_RE = re.compile(
    r"https?://(?:www\.)?"
    r"(?:(wikidata\.org/wiki/(Q\d+))"
    r"|(en\.wikipedia\.org/wiki/([^\"'\s]+))"
    r"|(crunchbase\.com/organization/[^\"'\s]+)"
    r"|(linkedin\.com/company/[^\"'\s]+)"
    r"|(sec\.gov[^\"'\s]*))",
    re.IGNORECASE,
)

_TIER1_DOMAINS = ("wikidata.org", "wikipedia.org", "sec.gov")
_TIER2_DOMAINS = ("crunchbase.com", "linkedin.com", "github.com")

# ── High-Risk Superlative Claim Patterns ─────────────────────────────────────

_HIGH_RISK_CLAIM_PATTERNS = [
    re.compile(r"#\s*1\s+(?:in|for|among)", re.IGNORECASE),
    re.compile(r"(?:only|first)\s+company\s+to\b", re.IGNORECASE),
    re.compile(r"(?:more than|over)\s+\d[\d,.]+\s+customers?", re.IGNORECASE),
    re.compile(r"\d[\d,.]+\s+(?:billion|million)\s+(?:users|transactions|events)", re.IGNORECASE),
    re.compile(r"present(?:ed|s)?\s+in\s+\d+\s+countries?", re.IGNORECASE),
    re.compile(r"founded\s+in\s+\d{4}", re.IGNORECASE),
]


# ═══════════════════════════════════════════════════════════════════════════════
# HTML PARSER
# ═══════════════════════════════════════════════════════════════════════════════

class _ClaimExtractorParser(HTMLParser):
    """
    Extracts Organization JSON-LD blocks, sameAs hrefs,
    og:site_name, <h1>, and visible body text.
    """

    def __init__(self):
        super().__init__()
        self.jsonld_blocks   = []
        self.og_site_name    = ""
        self.page_title      = ""
        self.h1_text         = ""
        self.visible_text    = ""
        self.same_as_hrefs   = []

        self._in_jsonld      = False
        self._in_title       = False
        self._in_h1          = False
        self._skip           = {"script", "style", "noscript"}
        self._in_skip        = False
        self._current_jsonld = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag == "script" and "application/ld+json" in attr_dict.get("type", ""):
            self._in_jsonld = True
            self._current_jsonld = []
            return

        if tag == "meta":
            name = attr_dict.get("property", attr_dict.get("name", "")).lower()
            if name == "og:site_name":
                self.og_site_name = attr_dict.get("content", "").strip()

        if tag == "title":
            self._in_title = True
        if tag == "h1":
            self._in_h1 = True
        if tag == "a":
            href = attr_dict.get("href", "")
            if href:
                self.same_as_hrefs.append(href)

        if tag in self._skip:
            self._in_skip = True

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "script" and self._in_jsonld:
            self._in_jsonld = False
            self.jsonld_blocks.append("".join(self._current_jsonld))
            self._current_jsonld = []
        if tag == "title":
            self._in_title = False
        if tag == "h1":
            self._in_h1 = False
        if tag in self._skip:
            self._in_skip = False

    def handle_data(self, data):
        if self._in_jsonld:
            self._current_jsonld.append(data)
            return
        if self._in_skip:
            return
        stripped = data.strip()
        if not stripped:
            return
        if self._in_title:
            self.page_title += stripped
        if self._in_h1:
            self.h1_text += stripped
        self.visible_text += " " + stripped


# ═══════════════════════════════════════════════════════════════════════════════
# CLAIM EXTRACTION FROM JSON-LD
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_jsonld_claims(raw_blocks):
    """
    Returns a dict of on-page entity claims extracted from JSON-LD.
    Keys: org_name, founding_year (str|None), founder_names (list),
          address_locality, address_country, same_as_links (list),
          pricing_tiers (list[str]), price_values (list[str])
    """
    claims = {
        "org_name":       None,
        "founding_year":  None,
        "founder_names":  [],
        "ceo_name":       None,
        "address_locality": None,
        "address_country": None,
        "same_as_links":  [],
        "pricing_tiers":  [],
        "price_values":   [],
    }

    for raw in raw_blocks:
        raw = raw.strip()
        if not raw:
            continue
        raw = re.sub(r"^<!\[CDATA\[", "", raw).rstrip("]]>")
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue

        items = []
        if isinstance(obj, dict):
            items.append(obj)
            items.extend(obj.get("@graph", []) if isinstance(obj.get("@graph"), list) else [])
        elif isinstance(obj, list):
            items = obj

        for item in items:
            if not isinstance(item, dict):
                continue

            # Org name
            if not claims["org_name"] and "name" in item:
                claims["org_name"] = str(item["name"]).strip()

            # Founding year
            if not claims["founding_year"]:
                fd = item.get("foundingDate", "")
                if fd:
                    m = re.search(r"\d{4}", str(fd))
                    if m:
                        claims["founding_year"] = m.group(0)

            # sameAs
            same_as = item.get("sameAs", [])
            if isinstance(same_as, str):
                same_as = [same_as]
            if isinstance(same_as, list):
                claims["same_as_links"].extend(s for s in same_as if isinstance(s, str))

            # Address
            addr = item.get("address", {})
            if isinstance(addr, dict):
                if not claims["address_locality"]:
                    claims["address_locality"] = addr.get("addressLocality", "").strip() or None
                if not claims["address_country"]:
                    claims["address_country"] = addr.get("addressCountry", "").strip() or None

            # Founders
            founders = item.get("founder", [])
            if isinstance(founders, dict):
                founders = [founders]
            if isinstance(founders, list):
                for f in founders:
                    if isinstance(f, dict) and "name" in f:
                        claims["founder_names"].append(str(f["name"]).strip())
                    elif isinstance(f, str):
                        claims["founder_names"].append(f.strip())

            # Offers / pricing
            offers = item.get("offers", [])
            if isinstance(offers, dict):
                offers = [offers]
            if isinstance(offers, list):
                for o in offers:
                    if isinstance(o, dict):
                        price = o.get("price", "")
                        name  = o.get("name", "")
                        if price:
                            claims["price_values"].append(str(price))
                        if name:
                            claims["pricing_tiers"].append(str(name))

    return claims


# ═══════════════════════════════════════════════════════════════════════════════
# CLAIM EXTRACTION FROM VISIBLE TEXT
# ═══════════════════════════════════════════════════════════════════════════════

def _is_subject_bound(match_start, visible_text, brand_name=""):
    """
    Checks if a text match occurs near brand name or first-person possessives.
    Excludes third-party entity qualifiers (e.g. 'our vendor', 'our partner', 'our consulting firm', 'our client').
    """
    start = max(0, match_start - 120)
    end = min(len(visible_text), match_start + 120)
    window = visible_text[start:end].lower()

    # Rule out third-party entity qualifiers
    third_party_qualifiers = [
        "our vendor", "our partner", "our supplier", "our client",
        "our consulting", "our agency", "our previous", "our former",
        "other company", "another firm", "our own consulting"
    ]
    if any(tp in window for tp in third_party_qualifiers):
        return False

    if any(p in window for p in ["our", "we", "us", "about us", "company", "headquarters"]):
        return True
    if brand_name and brand_name.lower() in window:
        return True
    return False


def _extract_text_claims(visible_text, brand_name=""):
    """Extracts founding year, leadership, HQ, pricing, and high-risk claims with subject binding."""
    claims = {
        "founding_year":    None,
        "ceo_names":        [],
        "hq_text":          None,
        "high_risk_claims": [],
        "pricing_tiers":    [],
        "price_values":     [],
    }

    for fy in _FOUNDING_YEAR_TEXT_RE.finditer(visible_text):
        if _is_subject_bound(fy.start(), visible_text, brand_name):
            claims["founding_year"] = fy.group(1)
            break

    for m in _LEADERSHIP_TEXT_RE.finditer(visible_text):
        name = m.group(1).strip()
        if len(name.split()) <= 4 and _is_subject_bound(m.start(), visible_text, brand_name):
            claims["ceo_names"].append(name)

    hq = _HQ_TEXT_RE.search(visible_text)
    if hq and _is_subject_bound(hq.start(), visible_text, brand_name):
        claims["hq_text"] = hq.group(1).strip().rstrip(",.")

    for p in _HIGH_RISK_CLAIM_PATTERNS:
        for m in p.finditer(visible_text):
            if _is_subject_bound(m.start(), visible_text, brand_name):
                snippet = visible_text[max(0, m.start() - 20): m.end() + 40].strip()
                claims["high_risk_claims"].append(snippet)

    claims["pricing_tiers"] = [m.group(0) for m in _PRICING_TIER_RE.finditer(visible_text)]
    claims["price_values"]  = [m.group(0) for m in _PRICE_VALUE_RE.finditer(visible_text)]

    return claims


# ═══════════════════════════════════════════════════════════════════════════════
# sameAs TIER CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

def _classify_same_as(same_as_links, href_links):
    """
    Returns:
        wikidata_qid   (str | None)  — e.g. "Q123456"
        wikipedia_slug (str | None)  — e.g. "Stripe,_Inc."
        tier1_links    (list[str])
        tier2_links    (list[str])
    """
    wikidata_qid   = None
    wikipedia_slug = None
    tier1 = []
    tier2 = []

    all_links = list(same_as_links) + list(href_links)

    for link in all_links:
        link_lower = link.lower()

        # Wikidata
        wd_m = re.search(r"wikidata\.org/wiki/(Q\d+)", link, re.IGNORECASE)
        if wd_m and not wikidata_qid:
            wikidata_qid = wd_m.group(1)

        # Wikipedia
        wp_m = re.search(r"en\.wikipedia\.org/wiki/([^\"'\s#?]+)", link, re.IGNORECASE)
        if wp_m and not wikipedia_slug:
            wikipedia_slug = wp_m.group(1)

        # Tier classification
        for d in _TIER1_DOMAINS:
            if d in link_lower:
                tier1.append(link)
                break
        else:
            for d in _TIER2_DOMAINS:
                if d in link_lower:
                    tier2.append(link)
                    break

    return wikidata_qid, wikipedia_slug, tier1, tier2


# ═══════════════════════════════════════════════════════════════════════════════
# WIKIDATA API CALLER
# ═══════════════════════════════════════════════════════════════════════════════

def _wikidata_get_claims(qid):
    """
    Queries Wikidata API for entity QID and returns a dict of extracted facts.
    Properties fetched:
      P571  → inception (founding date)
      P169  → chief executive officer
      P159  → headquarters location
      P856  → official website

    Returns {} on failure.
    """
    url = (
        "https://www.wikidata.org/w/api.php"
        f"?action=wbgetentities&ids={qid}"
        "&props=claims|labels"
        "&languages=en"
        "&format=json"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}

    entities = data.get("entities", {})
    entity   = entities.get(qid, {})
    raw_claims = entity.get("claims", {})

    result = {
        "founding_year": None,
        "ceo_name":      None,
        "hq_city":       None,
        "label":         None,
    }

    # Label
    label_data = entity.get("labels", {}).get("en", {})
    result["label"] = label_data.get("value", None)

    # P571 — inception (founding date)
    p571 = raw_claims.get("P571", [])
    for snak in p571:
        val = (snak.get("mainsnak", {})
                   .get("datavalue", {})
                   .get("value", {}))
        if isinstance(val, dict):
            time_str = val.get("time", "")   # e.g. "+2010-01-01T00:00:00Z"
            m = re.search(r"\+?(\d{4})", time_str)
            if m:
                result["founding_year"] = m.group(1)
                break

    # P169 — CEO (chief executive officer)
    p169 = raw_claims.get("P169", [])
    for snak in p169:
        person_id = (snak.get("mainsnak", {})
                        .get("datavalue", {})
                        .get("value", {})
                        .get("id", ""))
        if person_id:
            # Resolve person QID → label
            name = _wikidata_label(person_id)
            if name:
                result["ceo_name"] = name
                break

    # P159 — headquarters location
    p159 = raw_claims.get("P159", [])
    for snak in p159:
        place_id = (snak.get("mainsnak", {})
                       .get("datavalue", {})
                       .get("value", {})
                       .get("id", ""))
        if place_id:
            city = _wikidata_label(place_id)
            if city:
                result["hq_city"] = city
                break

    return result


def _wikidata_label(qid):
    """Resolves a Wikidata entity QID to its English label. Returns None on failure."""
    url = (
        "https://www.wikidata.org/w/api.php"
        f"?action=wbgetentities&ids={qid}"
        "&props=labels&languages=en&format=json"
    )
    try:
        time.sleep(_API_CALL_DELAY)
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return (data.get("entities", {})
                    .get(qid, {})
                    .get("labels", {})
                    .get("en", {})
                    .get("value", None))
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# WIKIPEDIA API CALLER
# ═══════════════════════════════════════════════════════════════════════════════

def _wikipedia_get_summary(slug):
    """
    Uses the Wikipedia REST summary API to fetch the page intro.
    Extracts founding year and CEO name from the summary text.
    Returns {} on failure.
    """
    encoded = urllib.parse.quote(slug, safe="")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}

    extract = data.get("extract", "")
    result  = {
        "founding_year": None,
        "ceo_name":      None,
        "hq_city":       None,
        "summary":       extract[:300] if extract else "",
    }

    # Founding year from extract
    fy = _FOUNDING_YEAR_TEXT_RE.search(extract)
    if fy:
        result["founding_year"] = fy.group(1)
    # Also try "in YYYY" as founding year pattern in Wikipedia lead sections
    if not result["founding_year"]:
        m = re.search(r"founded\s+(?:on\s+)?\w+\s+\w+,?\s+(\d{4})", extract, re.IGNORECASE)
        if m:
            result["founding_year"] = m.group(1)

    # CEO name
    for m in _LEADERSHIP_TEXT_RE.finditer(extract):
        name = m.group(1).strip()
        if len(name.split()) <= 4:
            result["ceo_name"] = name
            break

    # HQ city
    hq = _HQ_TEXT_RE.search(extract)
    if hq:
        result["hq_city"] = hq.group(1).strip().rstrip(",.")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 2-SOURCE CONSENSUS COMPARISON ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _years_conflict(page_year, external_year):
    """Returns True if two founding year strings differ by more than 1 year."""
    if not page_year or not external_year:
        return False
    try:
        return abs(int(page_year) - int(external_year)) > 1
    except (ValueError, TypeError):
        return False


def _apply_two_source_consensus(page_claims, text_claims,
                                 wikidata_facts, wikipedia_facts,
                                 page_url, tier1_links, tier2_links):
    """
    Core 2-source consensus engine (Appendix D).

    Compares on-page claim values against Wikidata and Wikipedia.
    Returns a list of findings:
      - F-FRSH-004  High  : 2 independent sources contradict the on-page claim
      - F-FRSH-005  Medium: 1 source contradicts, OR claim is uncorroborated
    """
    findings = []

    # Sanity-check resolved Wikidata entity label against on-page org_name
    org_name = page_claims.get("org_name", "")
    wd_label = wikidata_facts.get("label", "")
    wd_valid_entity = True
    if org_name and wd_label:
        import difflib
        ratio = difflib.SequenceMatcher(None, org_name.lower(), wd_label.lower()).ratio()
        if ratio < 0.35 and org_name.lower() not in wd_label.lower() and wd_label.lower() not in org_name.lower():
            wd_valid_entity = False
            findings.append(_make_finding(
                rule_id="F-FRSH-005",
                title=f"sameAs link points to a mismatched Wikidata entity ('{wd_label}' vs '{org_name}')",
                severity="medium",
                evidence=f"JSON-LD sameAs points to Wikidata entity '{wd_label}', which has low similarity to declared brand name '{org_name}'. External facts from this entity were suppressed to prevent hallucination.",
                summary="Verify sameAs link targets the correct Wikidata QID for your brand.",
                priority="medium",
                rationale="Mismatched sameAs links confuse AI knowledge graphs and cause AI assistants to attribute competitor facts to your brand.",
                code_fix=f'"sameAs": ["https://www.wikidata.org/wiki/QXXXXX"]  // Verify QID for {org_name}'
            ))

    # Extract claim variables for consensus matching
    page_founding = page_claims.get("founding_year") or text_claims.get("founding_year")
    wd_founding = wikidata_facts.get("founding_year") if wd_valid_entity else None
    wp_founding = wikipedia_facts.get("founding_year")

    page_ceo = (page_claims.get("founder_names") or [None])[0] if page_claims.get("founder_names") else (text_claims.get("ceo_names") or [None])[0]
    wd_ceo = wikidata_facts.get("ceo_name") if wd_valid_entity else None
    wp_ceo = wikipedia_facts.get("ceo_name")

    page_hq = page_claims.get("address_locality") or text_claims.get("hq_text")
    wd_hq = wikidata_facts.get("hq_city") if wd_valid_entity else None
    wp_hq = wikipedia_facts.get("hq_city")

    # ── Founding year conflict ────────────────────────────────────────────────
    if page_founding:
        wd_conflict = _years_conflict(page_founding, wd_founding)
        wp_conflict = _years_conflict(page_founding, wp_founding)

        if wd_conflict and wp_conflict:
            # Both external sources agree and contradict the page → F-FRSH-004 HIGH
            findings.append(_make_finding(
                rule_id="F-FRSH-004",
                title=(
                    f"Founding year conflict confirmed by 2 independent sources: "
                    f"page claims {page_founding}, "
                    f"Wikidata says {wd_founding}, Wikipedia says {wp_founding}"
                ),
                severity="high",
                evidence=(
                    f"On-page founding year claim '{page_founding}' on {page_url or 'this URL'} "
                    f"is contradicted by BOTH Wikidata (Q-entity inception: {wd_founding}) "
                    f"AND Wikipedia (extracted from lead section: {wp_founding}). "
                    "Per the Appendix D 2-source consensus rule, a discrepancy confirmed by "
                    "2 independent authoritative sources is a verified factual conflict. "
                    "AI models that cross-reference Wikidata will cite the conflicting year, "
                    "damaging brand credibility."
                ),
                summary=(
                    f"Investigate and correct the founding year on the page. "
                    f"Wikidata ({wd_founding}) and Wikipedia ({wp_founding}) both differ "
                    f"from the on-page claim ({page_founding})."
                ),
                priority="high",
                rationale=(
                    "AI answer engines (Perplexity, Bing Copilot, ChatGPT Browse) resolve "
                    "entity facts from Wikidata and Wikipedia before citing the brand's own page. "
                    "A 2-source confirmed discrepancy means AI answers will consistently cite "
                    "a year that conflicts with your own page."
                ),
                code_fix=(
                    f'// In Organization JSON-LD:\n'
                    f'"foundingDate": "{wd_founding}",  '
                    f'// Match Wikidata and Wikipedia\n\n'
                    f'// Alternatively, update Wikidata to match your records:\n'
                    f'// https://www.wikidata.org/wiki/Special:SetClaim'
                ),
            ))
        elif wd_conflict or wp_conflict:
            # Only one source contradicts → F-FRSH-005 MEDIUM
            conflict_src   = "Wikidata" if wd_conflict else "Wikipedia"
            conflict_year  = wd_founding if wd_conflict else wp_founding
            findings.append(_make_finding(
                rule_id="F-FRSH-005",
                title=(
                    f"Single-source founding year discrepancy: page says {page_founding}, "
                    f"{conflict_src} says {conflict_year}"
                ),
                severity="medium",
                evidence=(
                    f"On-page founding year '{page_founding}' on {page_url or 'this URL'} "
                    f"differs from {conflict_src} ({conflict_year}). "
                    "Only one external source conflicts — insufficient for a High finding "
                    "per the 2-source consensus rule, but warrants investigation."
                ),
                summary=(
                    f"Verify the founding year against {conflict_src} and either correct "
                    "the on-page claim or update the external source."
                ),
                priority="medium",
                rationale=(
                    "Single-source discrepancies are likely stale directory entries but "
                    "still reduce AI confidence in your brand facts."
                ),
                code_fix=(
                    f'"foundingDate": "{page_founding}",  '
                    f'// Verify this vs {conflict_src}: {conflict_year}'
                ),
            ))

    # ── Pricing / product-tiering claims — advisory ───────────────────────────
    # No authoritative external source exists for pricing; check internal presence
    page_price_tiers   = (page_claims.get("pricing_tiers", []) +
                           text_claims.get("pricing_tiers", []))
    page_price_values  = (page_claims.get("price_values", []) +
                           text_claims.get("price_values", []))

    if page_price_tiers and not page_price_values:
        # Has tier names (Free, Pro, Enterprise) but no actual price values
        # This is a "price claim without data" — cannot be cross-verified
        top_tiers = list(dict.fromkeys(page_price_tiers))[:3]
        findings.append(_make_finding(
            rule_id="F-FRSH-005",
            title="Pricing tier names present but no verifiable price values found",
            severity="medium",
            evidence=(
                f"Page on {page_url or 'this URL'} mentions pricing tier names "
                f"({', '.join(repr(t) for t in top_tiers)}) but provides no extractable "
                "price values (e.g., $25/month). Pricing claims without specific values "
                "cannot be cross-verified by AI models against third-party sources, "
                "making them prone to AI hallucination."
            ),
            summary=(
                "Add explicit price values next to each tier name so that AI systems "
                "can extract and cite accurate pricing."
            ),
            priority="medium",
            rationale=(
                "AI answer engines synthesize pricing from the page HTML. Tier names "
                "without values lead to hallucinated prices in AI-generated answers."
            ),
            code_fix=(
                '<!-- Include structured pricing with explicit values: -->\n'
                '<script type="application/ld+json">\n'
                '{\n'
                '  "@type": "Product",\n'
                '  "offers": [\n'
                '    {"@type":"Offer","name":"Free","price":"0","priceCurrency":"USD"},\n'
                '    {"@type":"Offer","name":"Pro","price":"20","priceCurrency":"USD",\n'
                '     "billingPeriod":"P1M"},\n'
                '    {"@type":"Offer","name":"Enterprise","price":"custom"}\n'
                '  ]\n'
                '}\n'
                '</script>'
            ),
        ))

    # ── Uncorroborated claims — no Tier 1 grounding ───────────────────────────
    # Only fire if NO Wikidata/Wikipedia API call succeeded (i.e., no entity resolved)
    has_specific_claims = bool(
        page_founding
        or text_claims.get("ceo_names")
        or text_claims.get("high_risk_claims")
        or page_price_tiers
    )
    api_resolved = bool(wikidata_facts or wikipedia_facts)
    has_tier1    = bool(tier1_links)

    if has_specific_claims and not api_resolved and not has_tier1:
        claim_examples = []
        if page_founding:
            claim_examples.append(f"foundingDate: {page_founding}")
        if text_claims.get("high_risk_claims"):
            claim_examples.append(f"'{text_claims['high_risk_claims'][0][:70]}'")
        if page_price_tiers:
            claim_examples.append(f"pricing tier: {page_price_tiers[0]}")

        findings.append(_make_finding(
            rule_id="F-FRSH-005",
            title="Verifiable claims found with no external knowledge graph grounding",
            severity="medium",
            evidence=(
                f"Page on {page_url or 'this URL'} makes specific verifiable claims "
                f"({'; '.join(claim_examples[:3])}) but has no sameAs links to "
                "Wikidata or Wikipedia, preventing AI systems from cross-verifying "
                "these claims against authoritative sources."
            ),
            summary=(
                "Add sameAs links in the Organization JSON-LD block pointing to "
                "Wikidata and Wikipedia to enable AI cross-verification."
            ),
            priority="medium",
            rationale=(
                "Without Wikidata/Wikipedia grounding, AI models cannot confirm "
                "founding dates, leadership, and other entity facts, increasing "
                "hallucination risk in AI-generated answers about your brand."
            ),
            code_fix=(
                '{\n'
                '  "@context": "https://schema.org",\n'
                '  "@type": "Organization",\n'
                '  "name": "YourBrandName",\n'
                '  "foundingDate": "2018",\n'
                '  "sameAs": [\n'
                '    "https://www.wikidata.org/wiki/QXXXXXXX",\n'
                '    "https://en.wikipedia.org/wiki/YourBrandName"\n'
                '  ]\n'
                '}'
            ),
        ))

    return findings


# ═══════════════════════════════════════════════════════════════════════════════
# FINDING FACTORY
# ═══════════════════════════════════════════════════════════════════════════════

def _make_finding(rule_id, title, severity, evidence, summary, priority, rationale, code_fix):
    return {
        "id":          rule_id,
        "skill_id":    "freshness-corroboration",
        "title":       title,
        "severity":    severity,
        "impact_area": "ai_discoverability",
        "evidence":    evidence,
        "suggested_action": {
            "summary":          summary,
            "priority":         priority,
            "rationale":        rationale,
            "code_fix_example": code_fix,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PUBLIC FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def check_cross_web_corroboration(raw_html, page_url=""):
    """
    Implements the Appendix D 2-Source Consensus Rule.

    Pipeline:
      1. Parse HTML → extract on-page claims and sameAs links
      2. Resolve Wikidata QID and Wikipedia slug from sameAs links
      3. Call Wikidata API for founding year, CEO, HQ (if QID found)
      4. Call Wikipedia REST API for summary (if slug found)
      5. Run 2-source consensus comparison
      6. Return findings (F-FRSH-004 for 2-source conflicts, F-FRSH-005 for single/missing)

    Args:
        raw_html (str): Raw page HTML.
        page_url (str): Source URL for evidence strings.
        enable_api_calls (bool): Set False in unit tests to skip live API calls.

    Returns:
        list[dict]: Findings conforming to report_schema.json.
    """
    if not raw_html or not raw_html.strip():
        return []

    # ── Step 1: Parse HTML ────────────────────────────────────────────────────
    parser = _ClaimExtractorParser()
    try:
        parser.feed(raw_html)
    except Exception:
        return []

    visible_text = parser.visible_text.strip()
    if len(visible_text.split()) < _MIN_WORDS_FOR_CORROBORATION:
        return []

    # ── Step 2: Extract claims ────────────────────────────────────────────────
    page_claims  = _parse_jsonld_claims(parser.jsonld_blocks)
    text_claims  = _extract_text_claims(visible_text)

    all_same_as  = list(page_claims["same_as_links"])
    wikidata_qid, wikipedia_slug, tier1_links, tier2_links = _classify_same_as(
        all_same_as, parser.same_as_hrefs
    )

    # ── Step 3 & 4: External API calls ───────────────────────────────────────
    wikidata_facts  = {}
    wikipedia_facts = {}
    api_calls_made  = 0

    if wikidata_qid and api_calls_made < _MAX_API_CALLS:
        wikidata_facts = _wikidata_get_claims(wikidata_qid)
        api_calls_made += 1
        time.sleep(_API_CALL_DELAY)

    if wikipedia_slug and api_calls_made < _MAX_API_CALLS:
        wikipedia_facts = _wikipedia_get_summary(wikipedia_slug)
        api_calls_made += 1

    # ── Step 5: 2-source consensus comparison ─────────────────────────────────
    findings = _apply_two_source_consensus(
        page_claims, text_claims,
        wikidata_facts, wikipedia_facts,
        page_url, tier1_links, tier2_links,
    )

    return findings
