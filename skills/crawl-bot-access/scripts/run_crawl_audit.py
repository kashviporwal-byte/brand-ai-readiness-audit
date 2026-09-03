"""
Master Runner for Skill 1: crawl-bot-access
Integrates all crawlability checkers and provides both a standalone CLI
and the callable API for audit-orchestrator.

Rule IDs: F-CRAWL-001 through F-CRAWL-012
"""

import sys
import os
import json
import urllib.request
from urllib.parse import urljoin, urlparse

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from robots_txt_checker import check_robots_txt
from http_header_auditor import check_http_headers_and_meta
from sitemap_auditor import audit_sitemap_content
from llms_txt_checker import check_llms_txt


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 (BrandAIReadinessAuditor/1.0)"
}


def fetch_url_resource(url, timeout=5):
    """Safely fetches a text resource returning (content_str, status_code, headers_dict)."""
    try:
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            headers = dict(resp.headers.items())
            content = resp.read().decode("utf-8", errors="replace")
            return content, status, headers
    except urllib.error.HTTPError as e:
        return None, e.code, dict(e.headers.items()) if hasattr(e, "headers") else {}
    except Exception:
        return None, 0, {}


def audit_crawl_bot_access(site_context_or_url, page_url=""):
    """
    Callable interface for audit-orchestrator.
    Accepts:
      - A SiteContext dict (with 'target_url', 'raw_html', 'http_headers')
      - A URL string or HTML payload
    """
    findings = []
    target_url = ""
    raw_html = ""
    http_headers = {}

    if isinstance(site_context_or_url, dict):
        target_url = site_context_or_url.get("target_url", "") or page_url
        raw_html = site_context_or_url.get("raw_html", "")
        http_headers = site_context_or_url.get("http_headers", {})
    elif isinstance(site_context_or_url, str):
        if site_context_or_url.startswith(("http://", "https://")):
            target_url = site_context_or_url
        else:
            raw_html = site_context_or_url
            target_url = page_url

    if not target_url:
        return findings

    parsed = urlparse(target_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}/"

    # 1. Check HTTP Headers on target page
    header_findings = check_http_headers_and_meta(http_headers, raw_html, target_url)
    findings.extend(header_findings)

    # 2. Fetch robots.txt and llms manifests in parallel
    robots_url = urljoin(base_url, "robots.txt")
    llms_url = urljoin(base_url, "llms.txt")
    llms_full_url = urljoin(base_url, "llms-full.txt")

    from concurrent.futures import ThreadPoolExecutor

    fetch_jobs = {
        "robots": robots_url,
        "llms": llms_url,
        "llms_full": llms_full_url,
    }
    fetch_results = {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_key = {executor.submit(fetch_url_resource, url): key for key, url in fetch_jobs.items()}
        for future in future_to_key:
            key = future_to_key[future]
            try:
                fetch_results[key] = future.result()
            except Exception:
                fetch_results[key] = (None, 0, {})

    robots_content, robots_status, _ = fetch_results.get("robots", (None, 0, {}))

    # Determine sitemap URL: check if robots.txt explicitly declares Sitemap:
    sitemap_from_robots = None
    if robots_content:
        for line in robots_content.splitlines():
            line_str = line.strip()
            if line_str.lower().startswith("sitemap:"):
                declared_url = line_str.split(":", 1)[1].strip()
                if declared_url.startswith(("http://", "https://")):
                    sitemap_from_robots = declared_url
                    break
                elif declared_url:
                    sitemap_from_robots = urljoin(base_url, declared_url.lstrip("/"))
                    break

    sitemap_url = sitemap_from_robots if sitemap_from_robots else urljoin(base_url, "sitemap.xml")

    # 3. Audit robots.txt
    if robots_status == 404:
        findings.append({
            "id": "F-CRAWL-006",
            "skill_id": "crawl-bot-access",
            "title": "robots.txt file is missing (HTTP 404 Not Found)",
            "severity": "medium",
            "impact_area": "crawl_accessibility",
            "evidence": f"GET {robots_url} returned status 404. Crawlers receive no access guidelines.",
            "suggested_action": {
                "summary": "Create and publish a standard robots.txt file at the root of the domain.",
                "priority": "medium",
                "rationale": "Without a robots.txt file, AI search crawlers cannot determine authorized paths or locate sitemaps.",
                "code_fix_example": "User-agent: *\nAllow: /\n\nSitemap: " + sitemap_url
            }
        })
    elif robots_content:
        findings.extend(check_robots_txt(robots_content, base_url))

    # 4. Fetch and audit sitemap.xml
    sitemap_content, sitemap_status, _ = fetch_url_resource(sitemap_url)
    if sitemap_status == 200 and sitemap_content:
        findings.extend(audit_sitemap_content(sitemap_content, sitemap_url))
    elif sitemap_status == 404 or (sitemap_status != 200 and not sitemap_content):
        findings.append({
            "id": "F-CRAWL-007",
            "skill_id": "crawl-bot-access",
            "title": "XML sitemap is unreachable (HTTP 404 Not Found)",
            "severity": "high",
            "impact_area": "crawl_accessibility",
            "evidence": f"GET {sitemap_url} returned status {sitemap_status or 404}. No canonical URL list found.",
            "suggested_action": {
                "summary": "Generate and publish an XML sitemap at the declared location.",
                "priority": "high",
                "rationale": "XML sitemaps are essential for AI bots to discover non-linked and updated URLs.",
                "code_fix_example": "Sitemap: " + sitemap_url
            }
        })

    # 5. Audit /llms.txt and /llms-full.txt from parallel fetch
    llms_content, llms_status, _ = fetch_results.get("llms", (None, 0, {}))
    findings.extend(check_llms_txt(llms_content, "llms.txt", llms_status))

    llms_full_content, llms_full_status, _ = fetch_results.get("llms_full", (None, 0, {}))
    findings.extend(check_llms_txt(llms_full_content, "llms-full.txt", llms_full_status))

    return findings


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_crawl_audit.py <URL>")
        sys.exit(1)

    url = sys.argv[1]
    res = audit_crawl_bot_access(url)
    print(json.dumps(res, indent=2))
