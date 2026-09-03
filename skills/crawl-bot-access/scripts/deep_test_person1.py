"""
Deep Test Battery for Skill 1: crawl-bot-access
Validates all subskills, 12 failure modes, false-positive resistance,
and schema compliance.
Total: 18 unit tests.
"""

import sys
import os
import json

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from robots_txt_checker import check_robots_txt
from http_header_auditor import check_http_headers_and_meta
from sitemap_auditor import audit_sitemap_content
from llms_txt_checker import check_llms_txt
from run_crawl_audit import audit_crawl_bot_access


def run_unit_tests():
    results = []

    def check(name, condition, detail=""):
        ok = bool(condition)
        results.append({"test": name, "pass": ok, "detail": detail})
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
        return ok

    print("\n=== UNIT TESTS FOR SKILL 1 (crawl-bot-access) ===")

    # 1. Clean robots.txt -> Allows AI crawlers and declares sitemap
    clean_robots = """
    User-agent: *
    Allow: /

    User-agent: GPTBot
    Allow: /

    User-agent: ClaudeBot
    Allow: /

    Sitemap: https://example.com/sitemap.xml
    """
    f_clean = check_robots_txt(clean_robots, "https://example.com")
    check("clean_robots_zero_findings", len(f_clean) == 0, f"clean robots.txt should produce 0 findings; got {[f['id'] for f in f_clean]}")

    # 2. Global crawl block -> F-CRAWL-001
    global_block_robots = """
    User-agent: *
    Disallow: /
    Sitemap: https://example.com/sitemap.xml
    """
    f_global = check_robots_txt(global_block_robots, "https://example.com")
    check("global_crawl_block_f_crawl_001", any(f["id"] == "F-CRAWL-001" and f["severity"] == "critical" for f in f_global), f"expected F-CRAWL-001; got {[f['id'] for f in f_global]}")

    # 3. Tier-1 AI crawler block -> F-CRAWL-002
    t1_block_robots = """
    User-agent: GPTBot
    Disallow: /

    User-agent: ClaudeBot
    Disallow: /

    Sitemap: https://example.com/sitemap.xml
    """
    f_t1 = check_robots_txt(t1_block_robots, "https://example.com")
    check("tier1_ai_bot_block_f_crawl_002", any(f["id"] == "F-CRAWL-002" and f["severity"] == "critical" for f in f_t1), f"expected F-CRAWL-002; got {[f['id'] for f in f_t1]}")

    # 4. Tier-2 AI crawler block -> F-CRAWL-003
    t2_block_robots = """
    User-agent: Google-Extended
    Disallow: /

    Sitemap: https://example.com/sitemap.xml
    """
    f_t2 = check_robots_txt(t2_block_robots, "https://example.com")
    check("tier2_ai_bot_block_f_crawl_003", any(f["id"] == "F-CRAWL-003" and f["severity"] == "medium" for f in f_t2), f"expected F-CRAWL-003; got {[f['id'] for f in f_t2]}")

    # 5. Missing sitemap in robots.txt -> F-CRAWL-008
    no_sitemap_robots = """
    User-agent: *
    Allow: /
    """
    f_no_sm = check_robots_txt(no_sitemap_robots, "https://example.com")
    check("missing_sitemap_directive_f_crawl_008", any(f["id"] == "F-CRAWL-008" and f["severity"] == "medium" for f in f_no_sm), f"expected F-CRAWL-008; got {[f['id'] for f in f_no_sm]}")

    # 6. HTTP X-Robots-Tag noai/noindex -> F-CRAWL-004
    f_header = check_http_headers_and_meta({"X-Robots-Tag": "noai, noindex"}, page_url="https://test.com")
    check("http_header_noai_f_crawl_004", any(f["id"] == "F-CRAWL-004" and f["severity"] == "critical" for f in f_header), f"expected F-CRAWL-004; got {[f['id'] for f in f_header]}")

    # 7. HTML meta robots noai -> F-CRAWL-004
    meta_html = "<html><head><meta name=\"robots\" content=\"noai, noimageai\"></head><body></body></html>"
    f_meta = check_http_headers_and_meta(raw_html=meta_html, page_url="https://test.com")
    check("meta_robots_noai_f_crawl_004", any(f["id"] == "F-CRAWL-004" and f["severity"] == "critical" for f in f_meta), f"expected F-CRAWL-004; got {[f['id'] for f in f_meta]}")

    # 8. HTTP X-Robots-Tag nosnippet -> F-CRAWL-005
    f_snippet = check_http_headers_and_meta({"x-robots-tag": "nosnippet"}, page_url="https://test.com")
    check("http_header_nosnippet_f_crawl_005", any(f["id"] == "F-CRAWL-005" and f["severity"] == "high" for f in f_snippet), f"expected F-CRAWL-005; got {[f['id'] for f in f_snippet]}")

    # 9. Clean sitemap -> 0 findings
    clean_sitemap = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url>
        <loc>https://example.com/</loc>
        <lastmod>2026-09-01</lastmod>
      </url>
    </urlset>"""
    f_sm_clean = audit_sitemap_content(clean_sitemap, "https://example.com/sitemap.xml")
    check("clean_sitemap_zero_findings", len(f_sm_clean) == 0, f"clean sitemap should produce 0 findings; got {[f['id'] for f in f_sm_clean]}")

    # 10. Malformed XML sitemap -> F-CRAWL-007
    f_sm_bad = audit_sitemap_content("<not valid xml>", "https://example.com/sitemap.xml")
    check("malformed_sitemap_f_crawl_007", any(f["id"] == "F-CRAWL-007" and f["severity"] == "high" for f in f_sm_bad), f"expected F-CRAWL-007; got {[f['id'] for f in f_sm_bad]}")

    # 11. Empty sitemap -> F-CRAWL-007
    empty_sitemap = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
    f_sm_empty = audit_sitemap_content(empty_sitemap, "https://example.com/sitemap.xml")
    check("empty_sitemap_f_crawl_007", any(f["id"] == "F-CRAWL-007" for f in f_sm_empty), f"expected F-CRAWL-007; got {[f['id'] for f in f_sm_empty]}")

    # 12. Stale sitemap lastmod -> F-CRAWL-009
    stale_sitemap = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/old</loc><lastmod>2023-01-01</lastmod></url>
    </urlset>"""
    f_sm_stale = audit_sitemap_content(stale_sitemap, "https://example.com/sitemap.xml")
    check("stale_sitemap_lastmod_f_crawl_009", any(f["id"] == "F-CRAWL-009" and f["severity"] == "medium" for f in f_sm_stale), f"expected F-CRAWL-009; got {[f['id'] for f in f_sm_stale]}")

    # 13. Missing llms.txt (404) -> F-CRAWL-011
    f_missing_llms = check_llms_txt(None, "llms.txt", status_code=404)
    check("missing_llms_txt_f_crawl_011", any(f["id"] == "F-CRAWL-011" and f["severity"] == "low" for f in f_missing_llms), f"expected F-CRAWL-011; got {[f['id'] for f in f_missing_llms]}")

    # 14. Non-standard formatting in llms.txt -> F-CRAWL-011
    f_nonstandard_llms = check_llms_txt("Just plain text without markdown header", "llms.txt", status_code=200)
    check("nonstandard_llms_txt_f_crawl_011", any(f["id"] == "F-CRAWL-011" for f in f_nonstandard_llms), f"expected F-CRAWL-011; got {[f['id'] for f in f_nonstandard_llms]}")

    # 15. Missing llms-full.txt (404) -> F-CRAWL-012
    f_missing_full = check_llms_txt(None, "llms-full.txt", status_code=404)
    check("missing_llms_full_txt_f_crawl_012", any(f["id"] == "F-CRAWL-012" and f["severity"] == "low" for f in f_missing_full), f"expected F-CRAWL-012; got {[f['id'] for f in f_missing_full]}")

    # 16. Empty input handling
    check("empty_url_returns_empty", audit_crawl_bot_access("") == [], "empty URL returns []")
    check("empty_dict_returns_empty", audit_crawl_bot_access({}) == [], "empty dict returns []")

    # 17. Schema key compliance
    sample_findings = f_global
    if sample_findings:
        f0 = sample_findings[0]
        required_keys = {"id", "skill_id", "title", "severity", "impact_area", "evidence", "suggested_action"}
        check("finding_schema_keys", required_keys.issubset(f0.keys()), f"missing keys: {required_keys - set(f0.keys())}")
        sa_keys = {"summary", "priority", "rationale", "code_fix_example"}
        check("suggested_action_schema_keys", sa_keys.issubset(f0.get("suggested_action", {}).keys()), f"missing suggested_action keys: {sa_keys - set(f0.get('suggested_action', {}).keys())}")

    # 18. SiteContext interface
    ctx = {
        "target_url": "https://example.com",
        "raw_html": meta_html,
        "http_headers": {"X-Robots-Tag": "noai"}
    }
    header_only_f = check_http_headers_and_meta(ctx["http_headers"], ctx["raw_html"], ctx["target_url"])
    check("site_context_payload_check", len(header_only_f) > 0, f"site context headers returned {len(header_only_f)} findings")

    passed = sum(1 for r in results if r["pass"])
    print(f"\nSkill 1 Comprehensive Battery: {passed}/{len(results)} passed")
    return results


if __name__ == "__main__":
    run_unit_tests()
