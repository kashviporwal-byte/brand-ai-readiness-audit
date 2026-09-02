"""
Master Runner for Skill 4: freshness-corroboration
Provides both a standalone CLI and the callable API for audit-orchestrator.

Usage (CLI):
    python run_freshness_audit.py https://example.com
    python run_freshness_audit.py ./local_page.html
    python run_freshness_audit.py https://example.com --output report.json

API (called by audit-orchestrator):
    from run_freshness_audit import audit_freshness_corroboration
    findings = audit_freshness_corroboration(site_context_dict_or_html_string, page_url)
"""

import sys
import os
import json
import urllib.request

# Ensure sibling scripts are importable regardless of working directory
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from temporal_freshness_checker     import check_temporal_freshness
from cross_web_corroborator         import check_cross_web_corroboration
from information_density_evaluator  import check_information_density


def audit_freshness_corroboration(site_context_or_html, page_url=""):
    """
    Callable interface for audit-orchestrator.

    Accepts either:
      - An in-memory SiteContext dict (with keys 'raw_html', 'target_url', 'crawled_pages')
      - A raw HTML string for standalone or test invocations

    Fans the payload out to all three freshness subskill checkers and returns
    a unified, deduplicated list of finding dicts.

    Args:
        site_context_or_html (dict | str): Input payload.
        page_url             (str):        Source URL (used in evidence strings).

    Returns:
        list[dict]: Findings conforming to report_schema.json.
    """
    raw_html   = ""
    target_url = page_url

    if isinstance(site_context_or_html, dict):
        target_url = (
            site_context_or_html.get("target_url")
            or site_context_or_html.get("url")
            or page_url
        )
        raw_html = site_context_or_html.get("raw_html", "")
        # Support orchestrator SiteContext with crawled_pages list
        if not raw_html and "crawled_pages" in site_context_or_html:
            pages = site_context_or_html["crawled_pages"]
            if pages and isinstance(pages, list):
                raw_html = pages[0].get("raw_html", "")

    elif isinstance(site_context_or_html, str):
        raw_html = site_context_or_html

    findings = []
    if not raw_html:
        return findings

    # ── Fan out to all three subskill checkers ────────────────────────────────
    findings.extend(check_temporal_freshness(raw_html, target_url))          # 4.1
    findings.extend(check_cross_web_corroboration(raw_html, target_url))     # 4.2
    findings.extend(check_information_density(raw_html, target_url))         # 4.3

    # Deduplicate by rule ID (keep first occurrence)
    seen_ids = set()
    deduped = []
    for f in findings:
        if f["id"] not in seen_ids:
            seen_ids.add(f["id"])
            deduped.append(f)

    return deduped


# ── Standalone CLI helpers ────────────────────────────────────────────────────

def _fetch_url(url):
    """
    Polite read-only HTTP fetch for standalone CLI testing.
    Identifies as the BrandAIReadinessAuditor sandbox to respect robots.txt policies.
    """
    headers = {
        "User-Agent": (
            "BrandAIReadinessAuditor/1.0 "
            "(+https://agentskills.io; read-only sandbox; freshness-corroboration)"
        )
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=8.0) as response:
        return response.read().decode("utf-8", errors="replace")


def main():
    if len(sys.argv) < 2:
        print("Usage:   python run_freshness_audit.py <URL_OR_HTML_FILE> [--output FILE]")
        print("Example: python run_freshness_audit.py https://example.com")
        print("Example: python run_freshness_audit.py ./local_page.html --output report.json")
        sys.exit(1)

    target = sys.argv[1]
    output_file = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]

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

    print(f"[*] Running freshness-corroboration audit on {target_url}...")
    findings = audit_freshness_corroboration(html, target_url)

    output = {
        "skill":          "freshness-corroboration",
        "target":         target_url,
        "total_findings": len(findings),
        "findings":       findings,
    }

    result_str = json.dumps(output, indent=2)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as fh:
            fh.write(result_str)
        print(f"[*] Report written to {output_file}")
    else:
        print(result_str)


if __name__ == "__main__":
    main()
