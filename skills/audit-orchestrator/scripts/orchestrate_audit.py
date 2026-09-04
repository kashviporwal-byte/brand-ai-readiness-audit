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
# Adaptive Representative Page Selection Engine  v2.0
# Synthesized from 20 AI reviews across 4 rounds.
# 7 bugs found and patched before implementation.
# Zero site-specific rules. Works on any vertical.
# ---------------------------------------------------------------------------

UTILITY_NOISE_RE = re.compile(
    r'/(?:privacy|terms|cookie|cookies|legal|disclaimer|login|signin|signup|register|cart|checkout|account)\b',
    re.IGNORECASE
)
STATIC_ASSET_RE = re.compile(
    r'\.(?:png|jpg|jpeg|gif|svg|webp|css|js|pdf|zip|xml|txt|ico|woff|woff2|ttf|mp4|mp3)$',
    re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Cluster normalization regexes — ORDER MATTERS: DATE before VERSION
# ---------------------------------------------------------------------------

# DATE must be checked BEFORE VERSION to prevent 4-digit years matching version
# Matches: 2024, 2024-01, 2024/01, 2024-01-15 etc.
DATE_SEGMENT_RE = re.compile(
    r'^\d{4}$|^\d{4}[-/]\d{2}$|^\d{4}[-/]\d{2}[-/]\d{2}$'
)

# VERSION checked second (safe — 4-digit years already handled by DATE above)
# Matches: 3, 3.8, v2, v1.2.3, 10 (but NOT 2024 — date takes priority)
# Bug Fix (Gemini R3): Added \d{1,2} to catch single-digit versions like /3/
VERSION_SEGMENT_RE = re.compile(
    r'^(?:v?\d+(?:\.\d+)+|v\d+|\d{1,2})$',
    re.IGNORECASE
)

# LOCALE checked third — uses next path segment as real cluster
# Bug Fix (Gemini R3): Added re.IGNORECASE for /en-us/, /zh-cn/ etc.
# Bug Fix (DeepSeek R4): Expanded suffix to {2,4} for zh-Hans, zh-Hant
# Matches: en, de, en-us, en-US, zh-Hans, pt-BR etc.
LOCALE_SEGMENT_RE = re.compile(
    r'^[a-z]{2}(?:[-_][a-z]{2,4})?$',
    re.IGNORECASE
)

# Noise query params to strip (NOT full query string — preserves ?curid= etc.)
# Bug Fix (Claude R3): Full query strip broke MediaWiki ?curid=123 identity URLs
NOISE_PARAMS = {"page", "sort", "filter", "ref", "source", "campaign"}


def _strip_noise_params(url):
    """Strip pagination/tracking params. Preserve content-identity params like ?curid=."""
    parsed = urlparse(url)
    if not parsed.query:
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    kept = [
        part for part in parsed.query.split("&")
        if part.split("=")[0].lower() not in NOISE_PARAMS
        and not part.lower().startswith("utm_")
    ]
    clean_path = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if kept:
        return f"{clean_path}?{'&'.join(kept)}".rstrip("/")
    return clean_path.rstrip("/")


def _get_normalized_cluster(url):
    """
    Normalize a URL to its semantic cluster name.
    DATE → __archive__, VERSION → use next segment, LOCALE → use next segment.
    ORDER MATTERS: DATE checked before VERSION.
    """
    path = urlparse(url).path.strip("/")
    parts = [p for p in path.split("/") if p]
    if not parts:
        return "root"
    first = parts[0]
    # 1. DATE first (e.g. /2024/01/post → __archive__)
    if DATE_SEGMENT_RE.match(first):
        return "__archive__"
    # 2. VERSION second (e.g. /3/library → cluster=library, /3.8/tutorial → cluster=tutorial)
    if VERSION_SEGMENT_RE.match(first):
        return parts[1] if len(parts) > 1 else "__version__"
    # 3. LOCALE third (e.g. /en/products → cluster=products, /zh-Hans/about → cluster=about)
    if LOCALE_SEGMENT_RE.match(first):
        return parts[1] if len(parts) > 1 else "__locale__"
    # 4. Normal path (e.g. /products → cluster=products)
    return first


def _extract_main_content_links(raw_html, base_url, final_url):
    """
    Extract links from inside <main> or <article> tags.
    These get a +3.0 relevance boost in scoring.
    Kills Wikipedia sidebar noise generically — no site-specific rules needed.
    """
    main_links = set()
    if not raw_html:
        return main_links
    norm_base = base_url.rstrip("/")
    main_blocks = re.findall(
        r'<(?:main|article)\b[^>]*>(.*?)</(?:main|article)>',
        raw_html, re.IGNORECASE | re.DOTALL
    )
    for block in main_blocks:
        hrefs = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\']', block, re.IGNORECASE)
        for h in hrefs:
            abs_u = urljoin(final_url, h.strip())
            p = urlparse(abs_u)
            clean_u = f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")
            if clean_u.startswith(norm_base) and not STATIC_ASSET_RE.search(clean_u):
                main_links.add(clean_u)
    return main_links


def _is_tail_duplicate(cand_url, cand_cluster, selected):
    """
    Check if cand_url is a structural sibling of any already-selected URL.
    e.g. /3.7/library vs /3.8/library → same tail 'library' + same cluster → duplicate.
    e.g. /services/cardiology vs /services/orthopedics → different tails → NOT duplicate.
    Bug Fix (DeepSeek R4): Default empty tail to 'root' to avoid false matches on root URLs.
    Special case: semantic cluster roots (__version__, __archive__, __locale__) are
    ALWAYS duplicates with each other — their tail IS the version/date number itself,
    not a meaningful content segment (e.g. docs.python.org/3.2 vs docs.python.org/3.14).
    """
    # For semantic roots: any repeat in the same special cluster = duplicate
    if cand_cluster in ("__version__", "__archive__", "__locale__"):
        return any(s["cluster"] == cand_cluster for s in selected)
    url_tail = urlparse(cand_url).path.rstrip("/").split("/")[-1] or "root"
    return any(
        (urlparse(s["url"]).path.rstrip("/").split("/")[-1] or "root") == url_tail
        and s["cluster"] == cand_cluster
        for s in selected
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
    Adaptive Representative Page Selection Engine v2.0
    ===================================================
    Discovers up to max_pages representative secondary pages from any website.
    Uses 4 structural signals + semantic cluster normalization + path-tail diversity.

    Signals:
      1. Navigation Prominence  (+10 if in <nav>/<header>, +2 otherwise)
      2. Cluster Volume         (log2-scaled, max +5.0)
      3. Main Content Boost     (+3.0 if linked from <main>/<article>)
      4. Depth Penalty          (-2.0 per path level below root)

    Diversity:
      - Soft redundancy penalty (-8.0 per same cluster repeat)
      - Path-tail similarity check (rejects structural siblings like /3.7/lib vs /3.8/lib)
      - Fallback still applies tail-duplicate check (Bug Fix: Claude R3)

    Normalization:
      - DATE segments (/2024/) → __archive__ cluster
      - VERSION segments (/3/, /3.8/, /v2/) → use next path segment as cluster
      - LOCALE segments (/en/, /zh-Hans/) → use next path segment as cluster
      - Noise query params stripped; content-identity params preserved
      - Root URL excluded from secondary slots (Bug Fix: Gemini R3)
    """
    if not target_url.startswith(("http://", "https://")):
        return []

    parsed = urlparse(target_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}/"
    norm_base = base_url.rstrip("/")
    norm_target = target_url.rstrip("/")

    # ── SIGNAL SOURCE A: Primary nav/header links ──────────────────────────
    nav_links = extract_navigation_links(raw_html, base_url, target_url)

    # ── SIGNAL SOURCE D: Main content links (for +3 relevance boost) ───────
    main_links = _extract_main_content_links(raw_html, base_url, target_url)

    # ── SIGNAL SOURCE B: Sitemap discovery ─────────────────────────────────
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
                        sitemap_url = declared if declared.startswith(("http://", "https://")) \
                            else urljoin(base_url, declared.lstrip("/"))
                        break
    except Exception:
        pass

    candidate_urls = set(nav_links)

    try:
        req = urllib.request.Request(sitemap_url, headers={"User-Agent": DEFAULT_USER_AGENT})
        with urllib.request.urlopen(req, timeout=4) as resp:
            xml_bytes = resp.read()
            root_el = ET.fromstring(xml_bytes)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            has_ns = "http://www.sitemaps.org/schemas/sitemap/0.9" in xml_bytes.decode("utf-8", errors="ignore")

            sitemaps = root_el.findall(".//sm:sitemap", ns) if has_ns else root_el.findall(".//sitemap")
            urls = root_el.findall(".//sm:url", ns) if has_ns else root_el.findall(".//url")

            if sitemaps:
                for sm in sitemaps[:3]:
                    loc_el = sm.find("sm:loc", ns) if has_ns else sm.find("loc")
                    if loc_el is not None and loc_el.text:
                        try:
                            child_req = urllib.request.Request(
                                loc_el.text.strip(), headers={"User-Agent": DEFAULT_USER_AGENT}
                            )
                            with urllib.request.urlopen(child_req, timeout=3) as ch_resp:
                                ch_root = ET.fromstring(ch_resp.read())
                                urls.extend(
                                    ch_root.findall(".//sm:url", ns) if has_ns
                                    else ch_root.findall(".//url")
                                )
                        except Exception:
                            pass

            count = 0
            for u in urls:
                if count >= 500:  # Hard cap — prevents memory spike on huge sitemaps
                    break
                loc = u.find("sm:loc", ns) if has_ns else u.find("loc")
                if loc is not None and loc.text:
                    raw_u = loc.text.strip()
                    clean_u = _strip_noise_params(raw_u)
                    p = urlparse(clean_u)
                    clean_u = f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")
                    if (clean_u != norm_target and clean_u != norm_base
                            and clean_u.startswith(norm_base)
                            and not STATIC_ASSET_RE.search(clean_u)
                            and not UTILITY_NOISE_RE.search(clean_u)):
                        candidate_urls.add(clean_u)
                        count += 1
    except Exception:
        pass

    # ── SIGNAL SOURCE C: Fallback — all homepage hrefs ─────────────────────
    if raw_html:
        href_matches = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\']', raw_html, re.IGNORECASE)
        for h in href_matches:
            abs_url = urljoin(target_url, h.strip())
            clean_u = _strip_noise_params(abs_url)
            p = urlparse(clean_u)
            clean_u = f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")
            if (clean_u != norm_base and clean_u != norm_target
                    and clean_u.startswith(norm_base)
                    and not STATIC_ASSET_RE.search(clean_u)
                    and not UTILITY_NOISE_RE.search(clean_u)):
                candidate_urls.add(clean_u)

    if not candidate_urls:
        return []

    # ── SCORING: Build feature vectors for all candidates ──────────────────
    # Compute cluster volumes using NORMALIZED clusters (not raw top-level dir)
    norm_clusters = {}
    for u in candidate_urls:
        c = _get_normalized_cluster(u)
        norm_clusters[c] = norm_clusters.get(c, 0) + 1

    scored = []
    for u in candidate_urls:
        parts = [p for p in urlparse(u).path.strip("/").split("/") if p]
        cluster = _get_normalized_cluster(u)
        depth = len(parts)

        # Signal 1: Navigation Prominence
        nav_score = 10.0 if u in nav_links else 2.0

        # Signal 2: Cluster Volume (log-scaled)
        vol_score = min(5.0, math.log2(norm_clusters.get(cluster, 1) + 1))

        # Signal 3: Main Content Boost (kills Wikipedia sidebar noise generically)
        main_boost = 3.0 if u in main_links else 0.0

        # Signal 4: Depth Penalty
        depth_pen = max(0, depth - 1) * 2.0

        total = nav_score + vol_score + main_boost - depth_pen
        scored.append({"url": u, "score": total, "cluster": cluster})

    # ── SELECTION: Greedy diversity with path-tail similarity ───────────────
    # Bug Fix (Gemini R3): Exclude root URL from secondary slots
    scored = [c for c in scored if c["url"].rstrip("/") != norm_base]

    sorted_cands = sorted(scored, key=lambda x: x["score"], reverse=True)
    selected = []
    selected_clusters = {}

    # PRIMARY PASS: soft redundancy penalty + path-tail duplicate check
    for cand in sorted_cands:
        if len(selected) >= max_pages:
            break
        cluster = cand["cluster"]
        times_used = selected_clusters.get(cluster, 0)
        effective_score = cand["score"] - (times_used * 8.0)

        if _is_tail_duplicate(cand["url"], cluster, selected):
            continue  # Structural sibling (version/locale) — skip

        if effective_score > -15.0:
            selected.append(cand)
            selected_clusters[cluster] = times_used + 1

    # FALLBACK PASS: relax cluster constraint but still apply tail-duplicate check
    # Bug Fix (Claude R3): Original fallback skipped tail-duplicate check entirely
    if len(selected) < max_pages:
        for cand in sorted_cands:
            if len(selected) >= max_pages:
                break
            if cand in selected:
                continue
            if _is_tail_duplicate(cand["url"], cand["cluster"], selected):
                continue
            selected.append(cand)

    return [c["url"] for c in selected]


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
