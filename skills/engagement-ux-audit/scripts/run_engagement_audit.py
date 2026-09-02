"""
Master Runner for Skill 5: engagement-ux-audit
Coordinates the 4 on-site engagement and referral UX subskills:
- 5.1: Heading Anchor & Deep-Link Auditor (heading_anchor_auditor.py)
- 5.2: Above-The-Fold Value Clarity Auditor (viewport_clarity_checker.py)
- 5.3: Intrusive Friction & Modal Detector (interstitial_friction_detector.py)
- 5.4: Cognitive Readability & Scannability Scorer (readability_cognitive_scorer.py)

Usage (CLI):
    python run_engagement_audit.py https://example.com
    python run_engagement_audit.py ./local_page.html

API (called by audit-orchestrator):
    from run_engagement_audit import audit_engagement_ux
    findings = audit_engagement_ux(site_context_or_html, page_url)
"""

import sys
import os
import re
import json
import urllib.request

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from heading_anchor_auditor       import check_heading_anchors
from viewport_clarity_checker     import check_viewport_clarity
from interstitial_friction_detector import check_interstitial_friction
from readability_cognitive_scorer import check_cognitive_readability


def audit_engagement_ux(site_context_or_html, page_url=""):
    """
    Callable entrypoint for audit-orchestrator and standalone invocations.
    Accepts either:
      - An in-memory SiteContext dict (keys: 'raw_html', 'target_url', 'crawled_pages')
      - A raw HTML string
    Returns a unified list of finding dicts matching report_schema.json.
    """
    raw_html = ""
    target_url = page_url

    if isinstance(site_context_or_html, dict):
        target_url = (
            site_context_or_html.get("target_url")
            or site_context_or_html.get("url")
            or page_url
        )
        raw_html = site_context_or_html.get("raw_html", "")
        if not raw_html and "crawled_pages" in site_context_or_html:
            pages = site_context_or_html["crawled_pages"]
            if pages and isinstance(pages, list):
                raw_html = pages[0].get("raw_html", "")
    elif isinstance(site_context_or_html, str):
        raw_html = site_context_or_html

    findings = []
    if not raw_html:
        return findings

    # Fan out to all 4 subskill auditors
    findings.extend(check_heading_anchors(raw_html, target_url))          # Subskill 5.1
    findings.extend(check_viewport_clarity(raw_html, target_url))        # Subskill 5.2
    findings.extend(check_interstitial_friction(raw_html, target_url))   # Subskill 5.3
    findings.extend(check_cognitive_readability(raw_html, target_url))   # Subskill 5.4

    return findings


def _fetch_url(url):
    """Polite HTTP GET for standalone CLI testing."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(BrandAIReadinessAuditor/1.0; read-only sandbox; engagement-ux-audit)"
        )
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=8.0) as response:
        return response.read().decode("utf-8", errors="replace")


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_engagement_audit.py <URL_OR_HTML_FILE>")
        sys.exit(1)

    target = sys.argv[1]
    if os.path.isfile(target):
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
        url = os.path.abspath(target)
    else:
        url = target if re.match(r"^https?://", target, re.I) else f"https://{target}"
        print(f"[*] Fetching: {url} ...")
        html = _fetch_url(url)

    findings = audit_engagement_ux(html, url)
    print(f"\n=======================================================")
    print(f"ENGAGEMENT UX AUDIT RESULTS: {url}")
    print(f"Total Findings Detected: {len(findings)}")
    print(f"=======================================================")

    for i, f in enumerate(findings, 1):
        sev = f.get("severity", "LOW").upper()
        fid = f.get("id", "F-ENG-???")
        title = f.get("title", "")
        print(f"\n#{i:02d} [{sev:8}] {fid}: {title}")
        print(f"    Evidence : {f.get('evidence')}")
        print(f"    Action   : {f.get('suggested_action', {}).get('summary')}")

    out_file = "engagement_audit_result.json"
    with open(out_file, "w", encoding="utf-8") as out:
        json.dump(findings, out, indent=2)
    print(f"\n[OK] Results written to {out_file}")


if __name__ == "__main__":
    main()
