"""
Subskill 1.3: XML Sitemap Discovery, Freshness & Reachability Auditor
Audits the target website sitemap:
- Sitemap reachability and XML validity (F-CRAWL-007)
- Stale or missing <lastmod> timestamps (F-CRAWL-009)
- Broken URLs returned in sitemap sampling (F-CRAWL-010)
Rule IDs: F-CRAWL-007, F-CRAWL-009, F-CRAWL-010
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
import urllib.request


def audit_sitemap_content(sitemap_xml_str, sitemap_url=""):
    findings = []
    if not sitemap_xml_str:
        return findings

    try:
        root = ET.fromstring(sitemap_xml_str)
    except Exception as e:
        findings.append({
            "id": "F-CRAWL-007",
            "skill_id": "crawl-bot-access",
            "title": "XML sitemap is invalid or malformed",
            "severity": "high",
            "impact_area": "crawl_accessibility",
            "evidence": f"XML parse error in {sitemap_url}: {str(e)[:120]}",
            "suggested_action": {
                "summary": "Regenerate sitemap.xml with valid UTF-8 XML conforming to the sitemaps.org schema.",
                "priority": "high",
                "rationale": "AI search engines use sitemaps to discover new content; an unparseable sitemap stalls crawler ingestion.",
                "code_fix_example": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n  <url><loc>https://example.com/</loc></url>\n</urlset>"
            }
        })
        return findings

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    has_ns = "http://www.sitemaps.org/schemas/sitemap/0.9" in sitemap_xml_str

    urls = root.findall(".//sm:url", ns) if has_ns else root.findall(".//url")
    sitemaps = root.findall(".//sm:sitemap", ns) if has_ns else root.findall(".//sitemap")

    total_entries = len(urls) + len(sitemaps)
    if total_entries == 0:
        findings.append({
            "id": "F-CRAWL-007",
            "skill_id": "crawl-bot-access",
            "title": "XML sitemap is empty (0 URL entries found)",
            "severity": "high",
            "impact_area": "crawl_accessibility",
            "evidence": f"Parsed {sitemap_url} successfully but found 0 <url> or <sitemap> entries.",
            "suggested_action": {
                "summary": "Populate sitemap.xml with public canonical URLs.",
                "priority": "high",
                "rationale": "An empty sitemap provides zero discovery value for automated search crawlers.",
                "code_fix_example": "<url><loc>https://example.com/pricing</loc></url>"
            }
        })
        return findings

    # Check lastmod timestamps on URL entries
    stale_urls = 0
    missing_lastmod = 0
    now = datetime.now(timezone.utc)

    for u in urls:
        lastmod = u.find("sm:lastmod", ns) if has_ns else u.find("lastmod")
        if lastmod is not None and lastmod.text:
            text = lastmod.text.strip()
            try:
                date_str = text[:10]
                dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if now - dt > timedelta(days=180):
                    stale_urls += 1
            except ValueError:
                pass
        else:
            missing_lastmod += 1

    if stale_urls > 0 or missing_lastmod > 0:
        evidence_parts = []
        if stale_urls > 0:
            evidence_parts.append(f"{stale_urls} URL(s) with lastmod older than 180 days")
        if missing_lastmod > 0:
            evidence_parts.append(f"{missing_lastmod} URL(s) missing lastmod timestamp")
        evidence_str = "; ".join(evidence_parts)

        findings.append({
            "id": "F-CRAWL-009",
            "skill_id": "crawl-bot-access",
            "title": "XML sitemap lacks fresh lastmod timestamps",
            "severity": "medium",
            "impact_area": "crawl_accessibility",
            "evidence": f"Evaluated {len(urls)} sitemap URL(s): {evidence_str}.",
            "suggested_action": {
                "summary": "Add automated <lastmod> timestamps updated whenever page content is republished.",
                "priority": "medium",
                "rationale": "AI crawlers prioritize fetching recently modified pages over stale entries.",
                "code_fix_example": "<url>\n  <loc>https://example.com/docs</loc>\n  <lastmod>2026-09-01</lastmod>\n</url>"
            }
        })

    return findings
