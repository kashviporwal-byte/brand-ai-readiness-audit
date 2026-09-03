"""
Subskill 1.2: HTTP Response Header & Meta Robots Auditor
Audits X-Robots-Tag HTTP headers and HTML <meta name="robots"> tags for
directives that restrict AI search crawlers:
- noai, noimageai, noindex, unavailable_after (F-CRAWL-004)
- nosnippet (F-CRAWL-005)
Rule IDs: F-CRAWL-004, F-CRAWL-005
"""

import re


def check_http_headers_and_meta(headers_dict=None, raw_html=None, page_url=""):
    findings = []
    headers_dict = headers_dict or {}

    x_robots = headers_dict.get("X-Robots-Tag", headers_dict.get("x-robots-tag", "")).lower()

    # Also parse <meta name="robots"> from HTML if provided
    meta_robots = ""
    if raw_html:
        meta_match = re.search(r'<meta\s+[^>]*name=["\'](?:robots|googlebot|bingbot)["\'][^>]*content=["\']([^"\']+)["\']', raw_html, re.IGNORECASE)
        if not meta_match:
            meta_match = re.search(r'<meta\s+[^>]*content=["\']([^"\']+)["\'][^>]*name=["\'](?:robots|googlebot|bingbot)["\']', raw_html, re.IGNORECASE)
        if meta_match:
            meta_robots = meta_match.group(1).lower()

    combined_directives = f"{x_robots} {meta_robots}".strip()
    if not combined_directives:
        return findings

    # 1. F-CRAWL-004: Restrictive AI / Indexing Directives
    if any(tag in combined_directives for tag in ["noai", "noindex", "noimageai", "unavailable_after"]):
        matched_tags = [t for t in ["noai", "noindex", "noimageai", "unavailable_after"] if t in combined_directives]
        findings.append({
            "id": "F-CRAWL-004",
            "skill_id": "crawl-bot-access",
            "title": "HTTP headers or meta tags contain restrictive AI blocking directives",
            "severity": "critical",
            "impact_area": "crawl_accessibility",
            "evidence": f"Found blocking directives: {', '.join(matched_tags)} (X-Robots-Tag: '{x_robots}', Meta: '{meta_robots}') on {page_url or 'target page'}.",
            "suggested_action": {
                "summary": "Remove 'noai', 'noindex', and 'noimageai' directives from public content pages.",
                "priority": "high",
                "rationale": "Directives like 'noai' and 'noindex' instruct AI crawlers to purge the page from their index and disregard citations.",
                "code_fix_example": "<!-- Replace: <meta name=\"robots\" content=\"noai, noindex\"> -->\n<meta name=\"robots\" content=\"index, follow\">"
            }
        })

    # 2. F-CRAWL-005: Snippet Suppression Directives
    if "nosnippet" in combined_directives:
        findings.append({
            "id": "F-CRAWL-005",
            "skill_id": "crawl-bot-access",
            "title": "HTTP headers or meta tags suppress text snippets (nosnippet)",
            "severity": "high",
            "impact_area": "crawl_accessibility",
            "evidence": f"Found 'nosnippet' directive on {page_url or 'target page'}. AI engines cannot extract answer passages.",
            "suggested_action": {
                "summary": "Remove 'nosnippet' directive and set appropriate max-snippet bounds.",
                "priority": "medium",
                "rationale": "AI answer engines require excerpt snippets to substantiate citations. Using 'nosnippet' causes the engine to cite competitors.",
                "code_fix_example": "<!-- Allow snippets: -->\n<meta name=\"robots\" content=\"max-snippet:-1, max-image-preview:large\">"
            }
        })

    return findings
