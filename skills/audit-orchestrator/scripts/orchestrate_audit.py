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
import math
import time
import argparse
import importlib.util
from datetime import datetime, timezone
import urllib.request
import urllib.error
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

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


# ---------------------------------------------------------------------------
# Dynamic 4-Signal Representative Page Selection Engine
# Eliminates keyword bias across any vertical (SaaS, Healthcare, Higher Ed, etc.)
# ---------------------------------------------------------------------------

UTILITY_NOISE_RE = re.compile(
    r'/(?:privacy|terms|cookie|cookies|legal|disclaimer|login|signin|signup|register|cart|checkout|account)\b',
    re.IGNORECASE
)
STATIC_ASSET_RE = re.compile(
    r'\.(?:png|jpg|jpeg|gif|svg|webp|css|js|pdf|zip|xml|txt|ico|woff|woff2|ttf|mp4|mp3)$',
    re.IGNORECASE
)


def extract_navigation_links(raw_html, base_url, final_url):
    """
    Extracts high-priority internal links from primary <header> and <nav> regions.
    Limits to the first 35 links to avoid giant footer mega-menu dilution.
    """
    if not raw_html:
        return set()
    nav_links = set()
    norm_base = base_url.rstrip("/")
    norm_target = final_url.rstrip("/")
    nav_blocks = re.findall(r'<(?:nav|header)\b[^>]*>(.*?)</(?:nav|header)>', raw_html, re.IGNORECASE | re.DOTALL)
    for block in nav_blocks:
        hrefs = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\']', block, re.IGNORECASE)
        for h in hrefs[:35]:
            abs_u = urljoin(final_url, h.strip())
            p = urlparse(abs_u)
            clean_u = f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")
            if clean_u != norm_base and clean_u != norm_target and clean_u.startswith(norm_base):
                if not STATIC_ASSET_RE.search(clean_u) and not UTILITY_NOISE_RE.search(clean_u):
                    nav_links.add(clean_u)
    return nav_links


def discover_high_intent_pages(target_url, raw_html="", max_pages=4):
    """
    Discovers representative secondary pages dynamically across ANY vertical.
    Uses a 4-Signal Structural Selection Engine:
      1. Primary Navigation Prominence (<header>/<nav> graph)
      2. Sitemap & Internal Link Cluster Density
      3. Path Depth Penalty (clean top-level routes over deeply buried URLs)
      4. Soft Section Diversity Penalty (Maximal Marginal Diagnostic Diversity)
    """
    if not target_url.startswith(("http://", "https://")):
        return []

    parsed = urlparse(target_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}/"
    norm_base = base_url.rstrip("/")
    norm_target = target_url.rstrip("/")

    # 1. Primary Navigation Prominence
    nav_links = extract_navigation_links(raw_html, base_url, target_url)

    # 2. Inspect robots.txt for declared sitemap location
    sitemap_url = urljoin(base_url, "sitemap.xml")
    robots_url = urljoin(base_url, "robots.txt")
    try:
        req = urllib.request.Request(robots_url, headers={"User-Agent": DEFAULT_USER_AGENT})
        with urllib.request.urlopen(req, timeout=3) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            for line in content.splitlines():
                line_str = line.strip()
                if line_str.lower().startswith("sitemap:"):
                    declared = line_str.split(":", 1)[1].strip()
                    if declared:
                        sitemap_url = declared if declared.startswith(("http://", "https://")) else urljoin(base_url, declared.lstrip("/"))
                        break
    except Exception:
        pass

    candidate_urls = set(nav_links)

    # 3. Fetch and parse sitemap
    try:
        req = urllib.request.Request(sitemap_url, headers={"User-Agent": DEFAULT_USER_AGENT})
        with urllib.request.urlopen(req, timeout=4) as resp:
            xml_bytes = resp.read()
            root = ET.fromstring(xml_bytes)
            ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            has_ns = 'http://www.sitemaps.org/schemas/sitemap/0.9' in xml_bytes.decode('utf-8', errors='ignore')

            # If sitemap index, peek up to 3 child sitemaps
            sitemaps = root.findall('.//sm:sitemap', ns) if has_ns else root.findall('.//sitemap')
            urls = root.findall('.//sm:url', ns) if has_ns else root.findall('.//url')
            if sitemaps:
                for sm in sitemaps[:3]:
                    loc_el = sm.find('sm:loc', ns) if has_ns else sm.find('loc')
                    if loc_el is not None and loc_el.text:
                        child_url = loc_el.text.strip()
                        try:
                            child_req = urllib.request.Request(child_url, headers={"User-Agent": DEFAULT_USER_AGENT})
                            with urllib.request.urlopen(child_req, timeout=3) as ch_resp:
                                ch_root = ET.fromstring(ch_resp.read())
                                urls.extend(ch_root.findall('.//sm:url', ns) if has_ns else ch_root.findall('.//url'))
                        except Exception:
                            pass

            for u in urls:
                loc = u.find('sm:loc', ns) if has_ns else u.find('loc')
                if loc is not None and loc.text:
                    url_str = loc.text.strip()
                    p = urlparse(url_str)
                    clean_u = f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")
                    if clean_u != norm_target and clean_u != norm_base and clean_u.startswith(norm_base):
                        if not STATIC_ASSET_RE.search(clean_u) and not UTILITY_NOISE_RE.search(clean_u):
                            candidate_urls.add(clean_u)
    except Exception:
        pass

    # 4. Fallback / supplement: extract from homepage hrefs
    if raw_html:
        href_matches = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\']', raw_html, re.IGNORECASE)
        for h in href_matches:
            abs_url = urljoin(target_url, h.strip())
            p = urlparse(abs_url)
            clean_u = f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")
            if clean_u != norm_base and clean_u != norm_target and clean_u.startswith(norm_base):
                if not STATIC_ASSET_RE.search(clean_u) and not UTILITY_NOISE_RE.search(clean_u):
                    candidate_urls.add(clean_u)

    if not candidate_urls:
        return []

    # 5. Compute directory cluster volume
    clusters = {}
    for u in candidate_urls:
        parts = [p for p in urlparse(u).path.strip("/").split("/") if p]
        c = parts[0] if parts else "root"
        clusters[c] = clusters.get(c, 0) + 1

    # 6. Maximal Marginal Diversity Greedy Selection
    selected = []
    selected_clusters = {}
    cands = list(candidate_urls)

    while len(selected) < max_pages and cands:
        best_u = None
        best_score = -999.0
        for u in cands:
            parts = [p for p in urlparse(u).path.strip("/").split("/") if p]
            c = parts[0] if parts else "root"
            depth = len(parts)

            # Signal 1: Primary Navigation Prominence
            nav_score = 10.0 if u in nav_links else 2.0

            # Signal 2: Directory Cluster Volume
            vol_score = min(5.0, math.log2(clusters.get(c, 1) + 1))

            # Signal 3: Depth Penalty (clean top-level paths win)
            depth_pen = max(0, depth - 1) * 2.0

            # Signal 4: Soft Redundancy Penalty (enforces cross-template diversity)
            red_pen = selected_clusters.get(c, 0) * 8.0

            total_score = nav_score + vol_score - depth_pen - red_pen
            if total_score > best_score:
                best_score = total_score
                best_u = u

        if best_u:
            selected.append(best_u)
            parts = [p for p in urlparse(best_u).path.strip("/").split("/") if p]
            c = parts[0] if parts else "root"
            selected_clusters[c] = selected_clusters.get(c, 0) + 1
            cands.remove(best_u)
        else:
            break

    return selected


def run_full_audit(target_url, quiet=False, multi_page=False, max_pages=5):
    """
    Main orchestration entrypoint. Fetches page, optionally discovers and crawls
    high-intent secondary pages (multi-page mode), runs all active skills,
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

    # 2. Fetch primary target page
    if not quiet:
        print(f"\n[*] Fetching primary target: {target_url} ...")
    page_data = fetch_target_page(target_url)
    raw_html = page_data["raw_html"]
    final_url = page_data["target_url"]

    crawled_pages = [{"url": final_url, "raw_html": raw_html, "status_code": page_data["status_code"]}]

    if not quiet:
        print(f"    -> Crawled {len(raw_html):,} bytes (HTTP {page_data['status_code']}) in {page_data['fetch_time']}s")

    # 2b. Multi-Page Discovery via sitemap (if enabled)
    if multi_page and max_pages > 1 and final_url.startswith(("http://", "https://")):
        if not quiet:
            print(f"\n[*] Multi-page mode enabled: discovering up to {max_pages - 1} secondary pages via sitemap...")
        secondary_urls = discover_high_intent_pages(final_url, raw_html, max_pages=max_pages - 1)
        if secondary_urls:
            if not quiet:
                for s_url in secondary_urls:
                    print(f"    -> Discovered high-intent page: {s_url}")
            with ThreadPoolExecutor(max_workers=min(len(secondary_urls), 4)) as fetcher:
                future_to_url = {fetcher.submit(fetch_target_page, u): u for u in secondary_urls}
                for f in as_completed(future_to_url):
                    try:
                        p_res = f.result()
                        crawled_pages.append({
                            "url": p_res["target_url"],
                            "raw_html": p_res["raw_html"],
                            "status_code": p_res["status_code"]
                        })
                    except Exception:
                        pass
        elif not quiet:
            print(f"    -> No additional secondary pages discovered (single-page audit applies).")

    site_context = {
        "target_url": final_url,
        "raw_html": raw_html,
        "crawled_pages": crawled_pages,
        "status_code": page_data["status_code"],
        "fetch_time": page_data["fetch_time"],
        "headers": page_data["headers"]
    }

    # 3. Fan out to active skills in parallel for primary page
    if not quiet:
        mode_str = f"{len(crawled_pages)} page(s)" if len(crawled_pages) > 1 else "target page"
        print(f"\n[*] Executing {len(active_skills)} active skill(s) concurrently on {mode_str}...")

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
                for f in res["findings"]:
                    if "page_url" not in f:
                        f["page_url"] = final_url
                    all_findings.append(f)
                if not quiet:
                    print(f"    [OK]  {res['skill_id']:28} -> {len(res['findings']):2} findings ({res['duration']}s)")

    # If multi-page, run page-level skills on secondary pages
    if len(crawled_pages) > 1:
        page_level_skills = [s for s in active_skills if s["id"] in ("render-extraction-audit", "freshness-corroboration", "engagement-ux-audit")]
        for sec_page in crawled_pages[1:]:
            sec_url = sec_page["url"]
            sec_ctx = {
                "target_url": sec_url,
                "raw_html": sec_page["raw_html"],
                "crawled_pages": crawled_pages,
                "status_code": sec_page.get("status_code", 200),
                "fetch_time": 0.1,
                "headers": {}
            }
            with ThreadPoolExecutor(max_workers=min(len(page_level_skills) or 1, 3)) as executor:
                futures = [executor.submit(execute_skill, skill, sec_ctx, sec_url) for skill in page_level_skills]
                for f in as_completed(futures):
                    res = f.result()
                    if not res["error"]:
                        for item in res["findings"]:
                            item["page_url"] = sec_url
                            all_findings.append(item)

    # 4. Deduplicate and sort findings
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    unique_findings = []
    seen_signatures = set()

    for f in all_findings:
        fid = f.get("id", "")
        p_url = f.get("page_url", final_url)
        sig = f"{fid}::{p_url}"
        if fid and sig not in seen_signatures:
            seen_signatures.add(sig)
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
    pages_list = [p["url"] for p in crawled_pages]
    crawl_mode_str = "multi-page" if (multi_page and len(pages_list) > 1) else "single-page"
    report = {
        "site": final_url,
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "crawl_mode": crawl_mode_str,
        "pages_audited": pages_list,
        "total_pages": len(pages_list),
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
    total_pages = report.get("total_pages", 1)

    print("\n" + "=" * 72)
    print(f"  AI READINESS AUDIT REPORT: {site}")
    print(f"  Audited At: {report['audited_at']} | Overall AI Score: {ai_score}/100")
    if total_pages > 1:
        print(f"  Scope: Multi-Page Site Audit ({total_pages} pages audited via sitemap traversal)")
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
            page_attr = f.get("page_url", "")

            print(f"\n  #{i:02d} [{sev:8}] {fid}: {title}")
            if total_pages > 1 and page_attr and page_attr != site:
                print(f"      Page     : {page_attr}")
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
    parser.add_argument("--multi-page", "-m", action="store_true", help="Audit key high-intent pages (pricing, docs, about) discovered from sitemap")
    parser.add_argument("--max-pages", type=int, default=5, help="Maximum number of pages to audit in multi-page mode (default: 5)")

    args = parser.parse_args()

    try:
        report, ai_score, _ = run_full_audit(
            args.url,
            quiet=args.quiet or args.json,
            multi_page=args.multi_page,
            max_pages=args.max_pages
        )

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
