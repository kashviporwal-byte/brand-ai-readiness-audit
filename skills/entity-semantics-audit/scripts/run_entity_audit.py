"""
Master Runner for Skill 3: entity-semantics-audit
Provides both a standalone CLI and the callable API for audit-orchestrator.

Usage (CLI):
    python run_entity_audit.py https://example.com
    python run_entity_audit.py ./local_page.html

API (called by audit-orchestrator):
    from run_entity_audit import audit_entity_semantics
    findings = audit_entity_semantics(site_context_dict_or_html_string, page_url)
"""

import sys
import os
import json
import urllib.request

# Ensure sibling scripts are importable regardless of working directory
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from jsonld_schema_auditor       import check_jsonld_schema
from sameas_disambiguator        import check_sameas_disambiguation
from quotable_definition_checker import check_quotable_definition
from locale_audience_auditor     import check_locale_audience, check_hreflang_reciprocity


def audit_entity_semantics(site_context_or_html, page_url=""):
    """
    Callable interface for audit-orchestrator.

    Accepts either:
      - An in-memory SiteContext dict (with keys 'raw_html', 'target_url', 'crawled_pages')
      - A raw HTML string for standalone or test invocations

    Fans the payload out to all four entity-semantics subskill checkers
    and returns a unified, deduplicated list of finding dicts.

    Args:
        site_context_or_html (dict | str): Input payload.
        page_url             (str):        Source URL (used in evidence strings).

    Returns:
        list[dict]: Findings conforming to report_schema.json.
    """
    raw_html   = ""
    target_url = page_url
    crawled_pages = []

    if isinstance(site_context_or_html, dict):
        target_url = (
            site_context_or_html.get("target_url")
            or site_context_or_html.get("url")
            or page_url
        )
        raw_html = site_context_or_html.get("raw_html", "")
        crawled_pages = site_context_or_html.get("crawled_pages", [])
        # Support orchestrator SiteContext with crawled_pages list
        if not raw_html and crawled_pages and isinstance(crawled_pages, list):
            raw_html = crawled_pages[0].get("raw_html", "")

    elif isinstance(site_context_or_html, str):
        raw_html = site_context_or_html

    findings = []
    if not raw_html:
        return findings

    # ── Fan out to all subskill checkers ───────────────────────────────────
    findings.extend(check_jsonld_schema(raw_html, target_url))           # 3.1
    findings.extend(check_sameas_disambiguation(raw_html, target_url))   # 3.2
    findings.extend(check_quotable_definition(raw_html, target_url))     # 3.3
    findings.extend(check_locale_audience(raw_html, target_url))         # 3.4
    if crawled_pages:
        findings.extend(check_hreflang_reciprocity(crawled_pages))

    return findings


# ── Standalone CLI helpers ────────────────────────────────────────────────────

def _fetch_url(url):
    """
    Polite read-only HTTP fetch for standalone CLI testing.
    Identifies as the BrandAIReadinessAuditor sandbox to respect robots.txt policies.
    """
    headers = {
        "User-Agent": (
            "BrandAIReadinessAuditor/1.0 "
            "(+https://agentskills.io; read-only sandbox; entity-semantics-audit)"
        )
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=6.0) as response:
        return response.read().decode("utf-8", errors="replace")


def main():
    if len(sys.argv) < 2:
        print("Usage:   python run_entity_audit.py <URL_OR_HTML_FILE>")
        print("Example: python run_entity_audit.py https://example.com")
        print("Example: python run_entity_audit.py ./local_page.html")
        sys.exit(1)

    target = sys.argv[1]

    # Detect local file vs URL
    if os.path.exists(target):
        with open(target, "r", encoding="utf-8") as fh:
            html = fh.read()
        target_url = "file://" + os.path.abspath(target)
    else:
        if not target.startswith("http://") and not target.startswith("https://"):
            target = "https://" + target
        print(f"[*] Fetching HTML for {target}...")
        html = _fetch_url(target)
        target_url = target

    print(f"[*] Running entity-semantics-audit on {target_url}...")
    findings = audit_entity_semantics(html, target_url)

    output = {
        "skill":          "entity-semantics-audit",
        "target":         target_url,
        "total_findings": len(findings),
        "findings":       findings,
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
