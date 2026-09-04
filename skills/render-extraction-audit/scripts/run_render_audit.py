"""
Master Runner for Skill 2: render-extraction-audit
Provides standalone execution and the callable API for audit-orchestrator.
"""

import sys
import os
import json
import urllib.request

# Ensure local imports work cleanly
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from dom_hydrator_diff import check_hydration_gap
from non_text_auditor import check_non_text_elements
from semantic_html_checker import check_semantic_hierarchy
from ua_cloaking_auditor import check_ua_cloaking


def audit_render_extraction(site_context_or_html, page_url=""):
    """
    Callable interface for audit-orchestrator.
    Accepts either an in-memory SiteContext dictionary or a raw HTML string.
    Returns a list of standardized finding dictionaries.
    """
    raw_html = ""
    target_url = page_url

    if isinstance(site_context_or_html, dict):
        # Extract from SiteContext
        target_url = site_context_or_html.get("target_url") or site_context_or_html.get("url") or page_url
        raw_html = site_context_or_html.get("raw_html", "")
        if not raw_html and "crawled_pages" in site_context_or_html and site_context_or_html["crawled_pages"]:
            raw_html = site_context_or_html["crawled_pages"][0].get("raw_html", "")
    elif isinstance(site_context_or_html, str):
        raw_html = site_context_or_html

    findings = []
    if not raw_html:
        return findings

    # Execute all subskills in memory
    findings.extend(check_hydration_gap(raw_html, target_url))
    findings.extend(check_non_text_elements(raw_html, target_url))
    findings.extend(check_semantic_hierarchy(raw_html, target_url))
    findings.extend(check_ua_cloaking(target_url, raw_html))

    return findings


def fetch_url(url):
    """Polite read-only fetch for standalone CLI testing."""
    headers = {
        "User-Agent": "BrandAIReadinessAuditor/1.0 (+https://agentskills.io; read-only sandbox)"
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=6.0) as response:
        return response.read().decode("utf-8", errors="replace")


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_render_audit.py <URL_OR_HTML_FILE>")
        print("Example: python run_render_audit.py https://example.com")
        sys.exit(1)

    target = sys.argv[1]
    if os.path.exists(target):
        with open(target, "r", encoding="utf-8") as f:
            html = f.read()
        target_url = "file://" + os.path.abspath(target)
    else:
        if not target.startswith("http://") and not target.startswith("https://"):
            target = "https://" + target
        print(f"[*] Fetching HTML for {target}...")
        html = fetch_url(target)
        target_url = target

    print(f"[*] Running render-extraction-audit on {target_url}...")
    findings = audit_render_extraction(html, target_url)

    output = {
        "skill": "render-extraction-audit",
        "target": target_url,
        "total_findings": len(findings),
        "findings": findings
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
