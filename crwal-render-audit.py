import argparse
import json
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta, timezone

def audit_crawl_access():
    parser = argparse.ArgumentParser(description="Production-grade AI crawlability audit.")
    parser.add_argument("--url", required=True, help="The base URL of the website to audit")
    args = parser.parse_args()

    base_url = args.url
    if not base_url.startswith(('http://', 'https://')):
        base_url = 'https://' + base_url
    if not base_url.endswith('/'):
        base_url += '/'

    findings = []
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })

    TIER_1_BOTS = {"gptbot", "claudebot", "perplexitybot"}
    TIER_2_BOTS = {"applebot-extended", "ccbot", "google-extended", "bytespider", "cohere-ai"}

    # --- Helper for Header Checks ---
    def check_headers(url, context_id="homepage"):
        try:
            resp = session.get(url, timeout=5, allow_redirects=True)
            x_robots = resp.headers.get("X-Robots-Tag", "").lower()
            if not x_robots:
                return None

            if any(tag in x_robots for tag in ["noai", "noindex", "noimageai", "unavailable_after"]):
                return {
                    "id": f"CRAWL-004-{context_id}",
                    "title": f"AI/Index Blocked via HTTP Header ({context_id})",
                    "severity": "critical",
                    "evidence": f"URL: {url} | X-Robots-Tag: {x_robots}",
                    "suggested_action": {
                        "summary": "Remove restrictive directives from X-Robots-Tag",
                        "priority": "high"
                    }
                }
            elif "nosnippet" in x_robots:
                return {
                    "id": f"CRAWL-005-{context_id}",
                    "title": f"AI Snippet Blocked via HTTP Header ({context_id})",
                    "severity": "high",
                    "evidence": f"URL: {url} | X-Robots-Tag: {x_robots}",
                    "suggested_action": {
                        "summary": "Remove 'nosnippet' from X-Robots-Tag",
                        "priority": "medium"
                    }
                }
        except Exception as e:
            return None
        return None

    # --- 1.1 AI User-Agent Directives (robots.txt) ---
    robots_content = None
    sitemap_from_robots = None
    try:
        resp = session.get(urljoin(base_url, "robots.txt"), timeout=5)
        if resp.status_code == 200:
            robots_content = resp.text
            for line in robots_content.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_from_robots = line.split(":", 1)[1].strip()
        elif resp.status_code == 404:
            findings.append({
                "id": "CRAWL-000",
                "title": "robots.txt Missing",
                "severity": "medium",
                "evidence": f"GET {urljoin(base_url, 'robots.txt')} returned 404",
                "suggested_action": {"summary": "Create a robots.txt file to explicitly manage AI crawler access", "priority": "medium"}
            })
    except Exception as e:
        findings.append({
            "id": "CRAWL-000-ERR",
            "title": "robots.txt Unreachable",
            "severity": "medium",
            "evidence": str(e),
            "suggested_action": {"summary": "Ensure robots.txt is accessible", "priority": "medium"}
        })

    if robots_content:
        # Correct Robot Group Modeling
        groups = [] # List of (set_of_agents, set_of_disallows)
        current_agents = set()
        current_disallows = set()

        for line in robots_content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"): continue

            if line.lower().startswith("user-agent:"):
                if current_agents or current_disallows:
                    groups.append((current_agents, current_disallows))
                current_agents = {line.split(":", 1)[1].strip().lower()}
            elif line.lower().startswith("disallow:"):
                path = line.split(":", 1)[1].strip()
                current_disallows.add(path)

        if current_agents or current_disallows:
            groups.append((current_agents, current_disallows))

        # Analyze blocks
        blocked_t1, blocked_t2 = set(), set()
        global_block = False

        for agents, disallows in groups:
            is_wildcard = "*" in agents
            has_full_block = any(p == "/" or p == "/*" for p in disallows)

            if is_wildcard and has_full_block:
                global_block = True

            for agent in agents:
                if agent == "*": continue
                if has_full_block:
                    if any(bot == agent for bot in TIER_1_BOTS): blocked_t1.add(agent)
                    elif any(bot == agent for bot in TIER_2_BOTS): blocked_t2.add(agent)

        if global_block:
            findings.append({
                "id": "CRAWL-001",
                "title": "Global AI Crawl Block",
                "severity": "critical",
                "evidence": "User-agent: * Disallow: / or /*",
                "suggested_action": {"summary": "Remove global block", "priority": "high"}
            })
        elif blocked_t1:
            findings.append({
                "id": "CRAWL-002",
                "title": "Tier-1 AI Bot Block",
                "severity": "critical",
                "evidence": f"Blocked: {', '.join(blocked_t1)}",
                "suggested_action": {"summary": "Allow Tier-1 AI crawlers", "priority": "high"}
            })
        elif blocked_t2:
            findings.append({
                "id": "CRAWL-003",
                "title": "Tier-2 AI Bot Block",
                "severity": "medium",
                "evidence": f"Blocked: {', '.join(blocked_t2)}",
                "suggested_action": {"summary": "Allow Tier-2 AI crawlers", "priority": "medium"}
            })

    # --- 1.2 X-Robots-Tag (Homepage) ---
    home_header_finding = check_headers(base_url, "homepage")
    if home_header_finding: findings.append(home_header_finding)

    # --- 1.3 Sitemap Availability, Freshness & URL reachability ---
    all_sitemap_urls = set()

    def fetch_sitemap_urls(url, depth=0):
        if depth > 3: return # Prevent infinite recursion
        try:
            resp = session.get(url, timeout=5)
            if resp.status_code != 200: return

            # Validate Content-Type to avoid HTML error pages
            if 'xml' not in resp.headers.get('Content-Type', '').lower():
                return

            root = ET.fromstring(resp.content)
            ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

            # Handle Sitemap Index
            sitemaps = root.findall('.//sm:sitemap', ns) if 'http://www.sitemaps.org/schemas/sitemap/0.9' in resp.text else root.findall('.//sitemap')
            for s in sitemaps:
                loc = s.find('sm:loc', ns) if 'http://www.sitemaps.org/schemas/sitemap/0.9' in resp.text else s.find('loc')
                if loc is not None: fetch_sitemap_urls(loc.text.strip(), depth + 1)

            # Handle URL entries
            urls = root.findall('.//sm:url', ns) if 'http://www.sitemaps.org/schemas/sitemap/0.9' in resp.text else root.findall('.//url')
            for u in urls:
                loc = u.find('sm:loc', ns) if 'http://www.sitemaps.org/schemas/sitemap/0.9' in resp.text else u.find('loc')
                if loc is not None: all_sitemap_urls.add(loc.text.strip())

                # Freshness check
                lastmod = u.find('sm:lastmod', ns) if 'http://www.sitemaps.org/schemas/sitemap/0.9' in resp.text else u.find('lastmod')
                if lastmod is not None and lastmod.text:
                    try:
                        dt = datetime.strptime(lastmod.text.strip()[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        if datetime.now(timezone.utc) - dt > timedelta(days=180):
                            if not any(f['id'] == 'CRAWL-009' for f in findings):
                                findings.append({
                                    "id": "CRAWL-009",
                                    "title": "Stale Sitemap Content",
                                    "severity": "medium",
                                    "evidence": f"Found URLs with lastmod older than 180 days in {url}",
                                    "suggested_action": {"summary": "Update sitemap.xml with recent lastmod timestamps", "priority": "medium"}
                                })
                    except ValueError: pass
                else:
                    if not any(f['id'] == 'CRAWL-009-MISSING' for f in findings):
                        findings.append({
                            "id": "CRAWL-009-MISSING",
                            "title": "Sitemap Missing lastmod",
                            "severity": "low",
                            "evidence": f"Some URLs in {url} are missing lastmod timestamps",
                            "suggested_action": {"summary": "Add lastmod timestamps to sitemap.xml for better AI discovery", "priority": "low"}
                        })

        except Exception: pass

    sitemap_url = sitemap_from_robots if sitemap_from_robots else urljoin(base_url, "sitemap.xml")
    fetch_sitemap_urls(sitemap_url)

    if not all_sitemap_urls:
        findings.append({
            "id": "CRAWL-007",
            "title": "Sitemap Unreachable or Empty",
            "severity": "high",
            "evidence": f"Could not extract URLs from {sitemap_url}",
            "suggested_action": {"summary": "Ensure sitemap.xml is valid and reachable", "priority": "high"}
        })
    elif not sitemap_from_robots:
        findings.append({
            "id": "CRAWL-008",
            "title": "Sitemap Omitted from robots.txt",
            "severity": "medium",
            "evidence": "Sitemap exists but not declared in robots.txt",
            "suggested_action": {"summary": "Add Sitemap directive to robots.txt", "priority": "low"}
        })

    # Reachability & Header Audit on sampled Sitemap URLs
    sampled_urls = list(all_sitemap_urls)[:15] # Sample 15 URLs
    broken_urls = []
    for url in sampled_urls:
        try:
            r = session.get(url, timeout=5)
            if r.status_code >= 400: broken_urls.append(f"{url} ({r.status_code})")
            # Check headers on sampled pages
            h_finding = check_headers(url, "sitemap_page")
            if h_finding: findings.append(h_finding)
        except Exception as e:
            broken_urls.append(f"{url} (Error)")

    if broken_urls:
        findings.append({
            "id": "CRAWL-010",
            "title": "Broken Sitemap URLs",
            "severity": "high",
            "evidence": f"Broken URLs found: {', '.join(broken_urls[:3])}...",
            "suggested_action": {"summary": "Fix broken links in sitemap.xml", "priority": "high"}
        })

    # --- 1.4 AI Discovery Standards (llms.txt) ---
    for filename in ["llms.txt", "llms-full.txt"]:
        url = urljoin(base_url, filename)
        fid = "CRAWL-011" if filename == "llms.txt" else "CRAWL-012"
        try:
            resp = session.get(url, timeout=5)
            if resp.status_code != 200:
                findings.append({
                    "id": fid, "title": f"Missing {filename}", "severity": "low",
                    "evidence": f"Status {resp.status_code}",
                    "suggested_action": {"summary": f"Add /{filename}", "priority": "low"}
                })
            else:
                content = resp.text.strip()
                ctype = resp.headers.get('Content-Type', '').lower()
                if not content or 'text' not in ctype:
                    findings.append({
                        "id": fid, "title": f"Invalid {filename} Content", "severity": "medium",
                        "evidence": f"File {filename} is empty or not text-based",
                        "suggested_action": {"summary": f"Ensure /{filename} is a non-empty text file", "priority": "low"}
                    })
                elif not content.startswith('#'):
                    findings.append({
                        "id": fid, "title": f"Non-standard {filename} Format", "severity": "low",
                        "evidence": f"File {filename} does not start with a markdown header (#)",
                        "suggested_action": {"summary": f"Format /{filename} as a markdown document", "priority": "low"}
                    })
        except Exception:
            findings.append({
                "id": fid, "title": f"Unreachable {filename}", "severity": "low",
                "evidence": "Connection failed", "suggested_action": {"summary": f"Add /{filename}", "priority": "low"}
            })

    print(json.dumps({"skill": "crawl-bot-access", "findings": findings}, indent=2))

if __name__ == "__main__":
    audit_crawl_access()
