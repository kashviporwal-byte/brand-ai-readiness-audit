#!/usr/bin/env python3
"""
Unit Test Runner for Brand AI-Readiness Audit Marketplace
Runs synthetic offline regression tests against all 5 domain skills and orchestrator.
Zero external network calls required.
"""

import sys
import os
import unittest

# Add project root and skill script directories to sys.path
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TEST_DIR)
SKILLS_DIR = os.path.join(PROJECT_ROOT, "skills")

for skill_name in os.listdir(SKILLS_DIR):
    scripts_dir = os.path.join(SKILLS_DIR, skill_name, "scripts")
    if os.path.isdir(scripts_dir) and scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

from http_header_auditor import check_http_headers_and_meta
from robots_txt_checker import check_robots_txt
from interstitial_friction_detector import check_interstitial_friction
from ua_cloaking_auditor import check_ua_cloaking
from run_render_audit import audit_render_extraction
from orchestrate_audit import run_full_audit


class TestBrandAIReadinessAudit(unittest.TestCase):

    def test_case_insensitive_x_robots_tag(self):
        """Bug #3 Regression: X-ROBOTS-TAG header casing lookup."""
        headers_upper = {"X-ROBOTS-TAG": "noindex, noai"}
        findings = check_http_headers_and_meta(headers_upper, raw_html="", page_url="https://example.com")
        f_ids = [f["id"] for f in findings]
        self.assertIn("F-CRAWL-004", f_ids, "Should detect restrictive AI directives in all-caps X-ROBOTS-TAG header")

    def test_robots_txt_allow_precedence(self):
        """Bug #2 Regression: Specific bot Allow: / overrides wildcard Disallow: /."""
        robots_txt = """
User-agent: *
Disallow: /

User-agent: GPTBot
Allow: /
"""
        findings = check_robots_txt(robots_txt, base_url="https://example.com/")
        f_ids = [f["id"] for f in findings]
        self.assertNotIn("F-CRAWL-001", f_ids, "Should NOT fire F-CRAWL-001 global block when Tier-1 bots are explicitly allowed")

    def test_single_modal_overlay_detection(self):
        """Bug #4 Regression: Single fixed 100% modal overlay detection."""
        fixture_path = os.path.join(TEST_DIR, "fixtures", "modal_overlay.html")
        with open(fixture_path, "r", encoding="utf-8") as f:
            html = f.read()
        findings = check_interstitial_friction(html, page_url="https://example.com")
        f_ids = [f["id"] for f in findings]
        self.assertIn("F-ENG-005", f_ids, "Should detect single full-screen modal overlay as intrusive friction")

    def test_ua_cloaking_generic_timeout_suppressed(self):
        """Bug #5 Regression: Generic network exception should NOT fire critical F-REND-014."""
        # Non-HTTP(S) local target url skips fetch cleanly
        findings = check_ua_cloaking("https://invalid-domain-that-does-not-exist-123456789.com", browser_html="<p>" + "word " * 100 + "</p>")
        f_ids = [f["id"] for f in findings]
        self.assertNotIn("F-REND-014", f_ids, "Generic transport exception should not fabricate F-REND-014 critical cloaking finding")

    def test_spa_hydration_trap_detection(self):
        """SPA Hydration Trap Detection."""
        fixture_path = os.path.join(TEST_DIR, "fixtures", "spa_shell.html")
        with open(fixture_path, "r", encoding="utf-8") as f:
            html = f.read()
        findings = audit_render_extraction(html, "https://example.com")
        f_ids = [f["id"] for f in findings]
        self.assertIn("F-REND-001", f_ids, "Should detect empty SPA shell as F-REND-001 hydration trap")

    def test_local_file_audit_no_fake_404(self):
        """Bug #1 Regression: Auditing local HTML file produces zero fake HTTP 404 network findings."""
        fixture_path = os.path.join(TEST_DIR, "fixtures", "clean_page.html")
        report, ai_score, _ = run_full_audit(fixture_path, quiet=True)
        evidence_all = " ".join(f.get("evidence", "") for f in report["findings"])
        self.assertNotIn("status 404", evidence_all.lower(), "Local file audit should not fabricate HTTP 404 status codes")
        self.assertNotIn("GET ://", evidence_all, "Local file audit should not build malformed :// URLs")
        self.assertGreaterEqual(ai_score, 70, "Clean page fixture should achieve score >= 70")


if __name__ == "__main__":
    unittest.main(verbosity=2)
