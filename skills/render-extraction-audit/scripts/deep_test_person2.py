"""Deep test battery for Person 2: render-extraction-audit"""
import sys
import os
import json
import time
import urllib.request

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from run_render_audit import audit_render_extraction, fetch_url
from dom_hydrator_diff import check_hydration_gap, clean_raw_html_fallback
from non_text_auditor import check_non_text_elements
from semantic_html_checker import check_semantic_hierarchy


def run_unit_tests():
    results = []

    def check(name, condition, detail=""):
        ok = bool(condition)
        results.append({"test": name, "pass": ok, "detail": detail})
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
        return ok

    print("\n=== UNIT TESTS ===")

    # BUG: corrupted regex \x01 instead of \1
    spa_html = (
        '<html><head><script>var x=function(){return "'
        + "a" * 500
        + '"}</script></head>'
        '<body><div id="root"></div><script src="/bundle.js"></script></body></html>'
    )
    fallback = clean_raw_html_fallback(spa_html)
    fallback_words = len(fallback.split())
    check(
        "fallback_strips_script_content",
        fallback_words < 10,
        f"fallback word count={fallback_words} (JS must not count as visible text)",
    )

    findings = check_hydration_gap(spa_html)
    check(
        "spa_empty_shell_critical",
        any(f["id"] == "F-REND-001" and f["severity"] == "critical" for f in findings),
        f"findings={[f['id'] for f in findings]}",
    )

    # False positive: SSR page with incidental root div
    rich_ssr = (
        "<html><body><main><h1>Test</h1><p>"
        + " word" * 200
        + '</p></main><div id="root"></div></body></html>'
    )
    f2 = check_hydration_gap(rich_ssr)
    check(
        "ssr_with_root_no_false_critical",
        not any(f["severity"] == "critical" for f in f2),
        f"findings={[f['id'] for f in f2]}",
    )

    decorative = (
        '<html><body>'
        '<img src="x.png" alt="" role="presentation">'
        '<img src="y.png" aria-hidden="true">'
        "</body></html>"
    )
    check(
        "decorative_images_skipped",
        len(check_non_text_elements(decorative)) == 0,
        "decorative imgs should not trigger F-REND-003",
    )

    fig = (
        "<html><body><figure>"
        '<img src="chart.png">'
        "<figcaption>Revenue grew 140 percent in Q4</figcaption>"
        "</figure></body></html>"
    )
    check(
        "figcaption_skips_alt_requirement",
        len(check_non_text_elements(fig)) == 0,
        "figure caption should satisfy accessibility",
    )

    audio = '<html><body><audio src="podcast.mp3"></audio></body></html>'
    f5 = check_non_text_elements(audio)
    check(
        "audio_transcript_check",
        any(f["id"] == "F-REND-005" for f in f5),
        f"audio without transcript should flag F-REND-005; got {[f['id'] for f in f5]}",
    )

    logo_h1 = (
        '<html><body><h1>'
        '<img src="logo.png" alt="Acme Corp Platform"></h1>'
        "</body></html>"
    )
    f6 = check_semantic_hierarchy(logo_h1)
    check(
        "logo_alt_in_h1",
        not any(f["id"] == "F-REND-006" for f in f6),
        f"H1 with logo alt should not be missing; got {[f['id'] for f in f6]}",
    )

    check("empty_html", audit_render_extraction("") == [], "empty string returns []")
    check("empty_dict", audit_render_extraction({}) == [], "empty dict returns []")

    ctx = {
        "target_url": "https://example.com",
        "raw_html": "<html><body><main><h1>Hi</h1></main></body></html>",
    }
    ctx_findings = audit_render_extraction(ctx)
    check(
        "orchestrator_dict_interface",
        isinstance(ctx_findings, list),
        f"dict interface works, {len(ctx_findings)} findings",
    )

    # Schema compliance
    sample = audit_render_extraction(
        '<html><body><img src="x.png"><h2>No id</h2></body></html>', "https://test.com"
    )
    if sample:
        f = sample[0]
        required = {"id", "skill_id", "title", "severity", "evidence", "suggested_action"}
        check(
            "finding_schema",
            required.issubset(f.keys()),
            f"missing keys: {required - set(f.keys())}",
        )
        sa_required = {"summary", "priority", "rationale", "code_fix_example"}
        check(
            "suggested_action_schema",
            sa_required.issubset(f.get("suggested_action", {}).keys()),
            f"suggested_action keys: {list(f.get('suggested_action', {}).keys())}",
        )

    passed = sum(1 for r in results if r["pass"])
    print(f"\nUnit tests: {passed}/{len(results)} passed")
    return results


def run_live_tests():
    sites = [
        ("https://example.com", "Minimal static"),
        ("https://react.dev", "React docs"),
        ("https://crates.io", "Ember SPA shell"),
        ("https://motherfuckingwebsite.com", "Ultra minimal"),
        ("https://info.cern.ch", "First web page"),
        ("https://stripe.com", "Heavy SaaS"),
        ("https://news.ycombinator.com", "HN legacy layout"),
        ("https://docs.python.org/3/", "Sphinx docs"),
        ("https://wikipedia.org", "Wikipedia portal"),
        ("https://vercel.com", "Next.js marketing"),
    ]

    print("\n=== LIVE SITE TESTS ===")
    results = []
    for url, label in sites:
        row = {"url": url, "label": label}
        try:
            t0 = time.time()
            html = fetch_url(url)
            row["fetch_s"] = round(time.time() - t0, 2)
            row["bytes"] = len(html)

            t1 = time.time()
            findings = audit_render_extraction(html, url)
            row["analysis_s"] = round(time.time() - t1, 3)
            row["count"] = len(findings)
            row["rules"] = sorted({f["id"] for f in findings})
            row["severities"] = {
                s: sum(1 for f in findings if f["severity"] == s)
                for s in ["critical", "high", "medium", "low"]
            }
            row["findings"] = findings
            print(
                f"  OK  {label:22} {row['count']:2} findings  "
                f"{row['analysis_s']:.3f}s  rules={row['rules']}"
            )
        except Exception as e:
            row["error"] = str(e)
            print(f"  ERR {label:22} {e}")
        results.append(row)

    return results


if __name__ == "__main__":
    unit = run_unit_tests()
    live = []
    if "--live" in sys.argv:
        live = run_live_tests()

    report = {
        "person": "Person 2 - render-extraction-audit",
        "unit_tests": unit,
        "live_tests": [
            {k: v for k, v in r.items() if k != "findings"} for r in live
        ],
    }
    out_path = os.path.join(script_dir, "..", "..", "..", "deep_test_person2_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport written to {out_path}")

