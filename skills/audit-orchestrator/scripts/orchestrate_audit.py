#!/usr/bin/env python3
"""
Master Audit Orchestrator for Brand AI-Readiness Audit
======================================================
Coordinates polite web crawling and fans out in-memory payloads to
domain skills. Synthesizes findings into a unified, deterministic
JSON audit report adhering to the contest report_schema.json.

Design:
- Dynamic auto-discovery: Runs all currently implemented skills (Skill 2, Skill 3).
- Forward-compatible: Automatically picks up Skills 1, 4, and 5 as soon as their
  runner scripts are placed into their respective folders.
- Concurrent execution: Fans out in parallel across all active skills via ThreadPoolExecutor.
- Zero external dependencies: Pure Python standard library.

Usage (CLI):
    python orchestrate_audit.py https://stripe.com
    python orchestrate_audit.py https://stripe.com --output report.json
    python orchestrate_audit.py ./local_page.html
"""

import sys
import os
import re
import json
import time
import argparse
import importlib.util
from datetime import datetime, timezone
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

# Determine paths relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ORCHESTRATOR_DIR = os.path.dirname(SCRIPT_DIR)
SKILLS_DIR = os.path.dirname(ORCHESTRATOR_DIR)
PROJECT_ROOT = os.path.dirname(SKILLS_DIR)
SCHEMA_PATH = os.path.join(ORCHESTRATOR_DIR, "references", "report_schema.json")

# User-Agent for polite, identified crawling
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36 (BrandAIReadinessAuditor/1.0; +https://agentskills.io)"
)

# Registry of all 5 domain skills defined in marketplace.json
SKILL_REGISTRY = [
    {
        "id": "crawl-bot-access",
        "name": "Crawl & Bot Accessibility",
        "dir": "crawl-bot-access",
        "module_candidates": ["run_crawl_audit", "crawl_bot_access_auditor", "audit_crawl"],
        "function_candidates": ["audit_crawl_bot_access", "audit_crawl_access", "run_audit"]
    },
    {
        "id": "render-extraction-audit",
        "name": "Machine Readability & Extraction",
        "dir": "render-extraction-audit",
        "module_candidates": ["run_render_audit"],
        "function_candidates": ["audit_render_extraction"]
    },
    {
        "id": "entity-semantics-audit",
        "name": "Entity Semantics & Knowledge Graph",
        "dir": "entity-semantics-audit",
        "module_candidates": ["run_entity_audit"],
        "function_candidates": ["audit_entity_semantics"]
    },
    {
        "id": "freshness-corroboration",
        "name": "Freshness & Cross-Web Corroboration",
        "dir": "freshness-corroboration",
        "module_candidates": ["run_freshness_audit", "freshness_corroboration_auditor", "audit_freshness"],
        "function_candidates": ["audit_freshness_corroboration", "audit_freshness", "run_audit"]
    },
    {
        "id": "engagement-ux-audit",
        "name": "On-Site Referral Engagement",
        "dir": "engagement-ux-audit",
        "module_candidates": ["run_engagement_audit", "engagement_ux_auditor", "audit_engagement"],
        "function_candidates": ["audit_engagement_ux", "audit_engagement", "run_audit"]
    }
]


def discover_available_skills():
    """
    Dynamically scans the skills directory and loads all ready domain skill runners.
    Returns a list of dicts: {"id", "name", "function", "script_path"}
    """
    discovered = []
    for entry in SKILL_REGISTRY:
        skill_dir = os.path.join(SKILLS_DIR, entry["dir"])
        scripts_dir = os.path.join(skill_dir, "scripts")
        if not os.path.isdir(scripts_dir):
            continue

        loaded_fn = None
        loaded_path = None

        for mod_name in entry["module_candidates"]:
            script_path = os.path.join(scripts_dir, f"{mod_name}.py")
            if os.path.isfile(script_path):
                try:
                    # Dynamically import module from file path
                    spec = importlib.util.spec_from_file_location(f"dyn_{entry['id']}", script_path)
                    module = importlib.util.module_from_spec(spec)
                    # Add scripts dir to sys.path during execution so module's local imports succeed
                    if scripts_dir not in sys.path:
                        sys.path.insert(0, scripts_dir)
                    spec.loader.exec_module(module)

                    # Look for callable function
                    for fn_name in entry["function_candidates"]:
                        if hasattr(module, fn_name) and callable(getattr(module, fn_name)):
                            loaded_fn = getattr(module, fn_name)
                            loaded_path = script_path
                            break
                    if loaded_fn:
                        break
                except Exception as e:
                    print(f"  [WARN] Failed to load candidate {script_path}: {e}", file=sys.stderr)

        if loaded_fn:
            discovered.append({
                "id": entry["id"],
                "name": entry["name"],
                "function": loaded_fn,
                "script_path": loaded_path
            })

    return discovered


def fetch_target_page(target_url, timeout=10.0):
    """
    Fetches the target webpage politely or reads from a local file.
    Returns a dict with 'raw_html', 'status_code', 'fetch_time', 'headers'.
    """
    t0 = time.time()

    # Local file support
    if os.path.isfile(target_url):
        with open(target_url, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return {
            "target_url": os.path.abspath(target_url),
            "raw_html": content,
            "status_code": 200,
            "fetch_time": round(time.time() - t0, 3),
            "headers": {"content-type": "text/html"}
        }

    # Ensure URL has protocol
    normalized_url = target_url
    if not re.match(r'^https?://', normalized_url, re.IGNORECASE):
        normalized_url = f"https://{normalized_url}"

    headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    req = urllib.request.Request(normalized_url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw_bytes = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            raw_html = raw_bytes.decode(charset, errors="replace")
            return {
                "target_url": response.geturl(),
                "raw_html": raw_html,
                "status_code": response.status,
                "fetch_time": round(time.time() - t0, 3),
                "headers": dict(response.headers)
            }
    except urllib.error.HTTPError as e:
        raw_bytes = e.read()
        raw_html = raw_bytes.decode("utf-8", errors="replace")
        return {
            "target_url": normalized_url,
            "raw_html": raw_html,
            "status_code": e.code,
            "fetch_time": round(time.time() - t0, 3),
            "headers": dict(e.headers) if hasattr(e, "headers") else {}
        }
    except Exception as e:
        raise RuntimeError(f"Network error fetching {normalized_url}: {e}")


def execute_skill(skill, site_context, target_url):
    """
    Safely executes a single domain skill and captures all findings.
    """
    t0 = time.time()
    skill_id = skill["id"]
    skill_name = skill["name"]
    fn = skill["function"]

    try:
        # Try calling with SiteContext dict first (preferred standard)
        try:
            findings = fn(site_context, target_url)
        except TypeError:
            # Fallback: call with raw_html string directly
            findings = fn(site_context["raw_html"], target_url)

        if not isinstance(findings, list):
            findings = []

        duration = round(time.time() - t0, 3)
        return {
            "skill_id": skill_id,
            "skill_name": skill_name,
            "findings": findings,
            "duration": duration,
            "error": None
        }
    except Exception as e:
        duration = round(time.time() - t0, 3)
        return {
            "skill_id": skill_id,
            "skill_name": skill_name,
            "findings": [],
            "duration": duration,
            "error": str(e)
        }


def calculate_ai_readiness_score(tallies):
    """
    Computes an overall AI Readiness Score from 0 to 100 based on weighted defect severity.
    """
    critical_penalty = tallies.get("critical", 0) * 25
    high_penalty = tallies.get("high", 0) * 10
    medium_penalty = tallies.get("medium", 0) * 4
    low_penalty = tallies.get("low", 0) * 1

    score = 100 - (critical_penalty + high_penalty + medium_penalty + low_penalty)
    return max(0, min(100, score))


def generate_proactive_recommendations(findings):
    """
    Synthesizes the top proactive recommendations from the highest severity findings.
    """
    recommendations = []
    seen_summaries = set()

    # Process critical and high findings first
    priority_findings = [f for f in findings if f.get("severity") in ("critical", "high")]
    if not priority_findings:
        priority_findings = [f for f in findings if f.get("severity") == "medium"]

    for f in priority_findings:
        sa = f.get("suggested_action", {})
        summary = sa.get("summary", "")
        if summary and summary not in seen_summaries:
            seen_summaries.add(summary)
            recommendations.append({
                "title": f.get("title", "Fix identified AI Discoverability issue"),
                "impact_area": f.get("impact_area", "ai_discoverability"),
                "summary": summary,
                "implementation_hint": sa.get("code_fix_example", sa.get("rationale", ""))
            })
            if len(recommendations) >= 3:
                break

    return recommendations


def run_full_audit(target_url, quiet=False):
    """
    Main orchestration entrypoint. Fetches page, runs all active skills,
    aggregates and deduplicates findings, and constructs the report schema.
    """
    # 1. Discover skills
    active_skills = discover_available_skills()
    active_ids = {s["id"] for s in active_skills}

    if not quiet:
        print(f"\n=================================================================")
        print(f"BRAND AI-READINESS AUDIT ORCHESTRATOR v1.0.0")
        print(f"=================================================================")
        print(f"[*] Discovering registered domain skills:")
        for reg in SKILL_REGISTRY:
            status = "ACTIVE" if reg["id"] in active_ids else "PENDING"
            marker = "[+]" if reg["id"] in active_ids else "[-]"
            print(f"    {marker} {reg['id']:28} -> {status}")

    # 2. Fetch page once
    if not quiet:
        print(f"\n[*] Fetching target: {target_url} ...")
    page_data = fetch_target_page(target_url)
    raw_html = page_data["raw_html"]
    final_url = page_data["target_url"]

    site_context = {
        "target_url": final_url,
        "raw_html": raw_html,
        "crawled_pages": [{"url": final_url, "raw_html": raw_html}],
        "status_code": page_data["status_code"],
        "fetch_time": page_data["fetch_time"],
        "headers": page_data["headers"]
    }

    if not quiet:
        print(f"    -> Crawled {len(raw_html):,} bytes (HTTP {page_data['status_code']}) in {page_data['fetch_time']}s")

    # 3. Fan out to active skills in parallel
    if not quiet:
        print(f"\n[*] Executing {len(active_skills)} active skill(s) concurrently...")

    all_findings = []
    execution_stats = []

    with ThreadPoolExecutor(max_workers=min(len(active_skills) or 1, 5)) as executor:
        future_to_skill = {
            executor.submit(execute_skill, skill, site_context, final_url): skill
            for skill in active_skills
        }
        for future in as_completed(future_to_skill):
            res = future.result()
            execution_stats.append(res)
            if res["error"]:
                if not quiet:
                    print(f"    [ERR] {res['skill_id']}: {res['error']}")
            else:
                all_findings.extend(res["findings"])
                if not quiet:
                    print(f"    [OK]  {res['skill_id']:28} -> {len(res['findings']):2} findings ({res['duration']}s)")

    # 4. Deduplicate and sort findings
    # Priority rank: critical -> high -> medium -> low
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    unique_findings = []
    seen_ids = set()

    for f in all_findings:
        fid = f.get("id", "")
        # Enforce canonical schema keys
        if fid and fid not in seen_ids:
            seen_ids.add(fid)
            unique_findings.append(f)

    unique_findings.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 4))

    # 5. Compute summary tallies
    tallies = {
        "total_findings": len(unique_findings),
        "critical": sum(1 for f in unique_findings if f.get("severity") == "critical"),
        "high": sum(1 for f in unique_findings if f.get("severity") == "high"),
        "medium": sum(1 for f in unique_findings if f.get("severity") == "medium"),
        "low": sum(1 for f in unique_findings if f.get("severity") == "low"),
    }

    ai_score = calculate_ai_readiness_score(tallies)

    # 6. Generate proactive recommendations
    recs = generate_proactive_recommendations(unique_findings)

    # 7. Construct final JSON report adhering strictly to report_schema.json
    report = {
        "site": final_url,
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "summary": tallies,
        "findings": unique_findings,
        "proactive_recommendations": recs
    }

    return report, ai_score, execution_stats


def print_terminal_dashboard(report, ai_score):
    """
    Renders a clean terminal summary card for users and CLI evaluators.
    """
    site = report["site"]
    summary = report["summary"]
    findings = report["findings"]

    print("\n" + "=" * 72)
    print(f"  AI READINESS AUDIT REPORT: {site}")
    print(f"  Audited At: {report['audited_at']} | Overall AI Score: {ai_score}/100")
    print(f"  Summary: {summary['total_findings']} issue(s) detected "
          f"[CRITICAL: {summary['critical']}, HIGH: {summary['high']}, "
          f"MEDIUM: {summary['medium']}, LOW: {summary['low']}]")
    print("=" * 72)

    if not findings:
        print("  🎉 PERFECT: No AI-discoverability defects detected on this page!")
    else:
        for i, f in enumerate(findings, 1):
            sev = f.get("severity", "LOW").upper()
            fid = f.get("id", "F-???")
            title = f.get("title", "")
            evidence = f.get("evidence", "")
            action = f.get("suggested_action", {})

            print(f"\n  #{i:02d} [{sev:8}] {fid}: {title}")
            print(f"      Evidence : {evidence}")
            print(f"      Action   : {action.get('summary', '')}")
            if action.get("code_fix_example"):
                first_line = action["code_fix_example"].strip().split("\n")[0]
                print(f"      Fix Hint : {first_line}")

    if report.get("proactive_recommendations"):
        print("\n" + "-" * 72)
        print("  TOP PROACTIVE RECOMMENDATIONS FOR AI REFERRAL CONVERSION:")
        print("-" * 72)
        for r in report["proactive_recommendations"]:
            print(f"  • {r['title']}")
            print(f"    {r['summary']}")
    print("=" * 72 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Master Orchestrator for Brand AI-Readiness Audit"
    )
    parser.add_argument("url", help="Target URL or path to local HTML file")
    parser.add_argument("--output", "-o", help="Optional path to save JSON audit report")
    parser.add_argument("--json", action="store_true", help="Print raw JSON report to stdout")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress progress logs")

    args = parser.parse_args()

    try:
        report, ai_score, _ = run_full_audit(args.url, quiet=args.quiet or args.json)

        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_terminal_dashboard(report, ai_score)

        if args.output:
            out_path = os.path.abspath(args.output)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            print(f"[OK] Full JSON report written to: {out_path}")

    except Exception as e:
        print(f"\n[ERROR] Audit failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
