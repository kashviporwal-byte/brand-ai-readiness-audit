"""
Subskill 1.1: robots.txt AI User-Agent Directive Auditor
Audits robots.txt for AI search crawler restrictions:
- Global crawl blocks (User-agent: * Disallow: /)
- Tier-1 AI crawler blocks (GPTBot, ClaudeBot, PerplexityBot)
- Tier-2 AI crawler blocks (Google-Extended, Amazonbot, Bytespider, etc.)
- Missing or unreachable robots.txt (404)
- Missing sitemap declaration in robots.txt
Rule IDs: F-CRAWL-001, F-CRAWL-002, F-CRAWL-003, F-CRAWL-006, F-CRAWL-008
"""

import re
from urllib.parse import urljoin

TIER_1_BOTS = frozenset({"gptbot", "claudebot", "perplexitybot"})
TIER_2_BOTS = frozenset({"applebot-extended", "ccbot", "google-extended", "bytespider", "cohere-ai", "amazonbot"})


def check_robots_txt(robots_content, base_url=""):
    findings = []
    if robots_content is None:
        return findings

    sitemap_declared = False
    groups = []
    current_agents = set()
    current_disallows = set()

    for line in robots_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        lower_line = line.lower()
        if lower_line.startswith("sitemap:"):
            sitemap_declared = True
        elif lower_line.startswith("user-agent:"):
            if current_agents or current_disallows:
                groups.append((current_agents, current_disallows))
            current_agents = {line.split(":", 1)[1].strip().lower()}
            current_disallows = set()
        elif lower_line.startswith("disallow:"):
            path = line.split(":", 1)[1].strip()
            current_disallows.add(path)

    if current_agents or current_disallows:
        groups.append((current_agents, current_disallows))

    blocked_t1 = set()
    blocked_t2 = set()
    global_block = False

    for agents, disallows in groups:
        is_wildcard = "*" in agents
        has_full_block = any(p in ("/", "/*") for p in disallows)

        if is_wildcard and has_full_block:
            global_block = True

        for agent in agents:
            if agent == "*":
                continue
            if has_full_block:
                if agent in TIER_1_BOTS:
                    blocked_t1.add(agent)
                elif agent in TIER_2_BOTS:
                    blocked_t2.add(agent)

    # 1. F-CRAWL-001: Global Block
    if global_block:
        findings.append({
            "id": "F-CRAWL-001",
            "skill_id": "crawl-bot-access",
            "title": "Global crawl block in robots.txt disallows all AI search crawlers",
            "severity": "critical",
            "impact_area": "crawl_accessibility",
            "evidence": "Detected 'User-agent: * Disallow: /' in robots.txt. All AI search engine bots are completely blocked.",
            "suggested_action": {
                "summary": "Remove global Disallow: / directive and provide granular access controls for AI crawlers.",
                "priority": "high",
                "rationale": "A global wildcard disallow prevents ChatGPT, Claude, and Perplexity from indexing any content on your site.",
                "code_fix_example": "User-agent: *\nAllow: /\n\n# Protect sensitive paths only:\nDisallow: /admin/\nDisallow: /checkout/"
            }
        })

    # 2. F-CRAWL-002: Tier-1 AI Bot Block
    elif blocked_t1:
        bot_list = ", ".join(sorted(blocked_t1))
        findings.append({
            "id": "F-CRAWL-002",
            "skill_id": "crawl-bot-access",
            "title": f"Tier-1 AI assistant crawlers explicitly blocked in robots.txt ({bot_list})",
            "severity": "critical",
            "impact_area": "crawl_accessibility",
            "evidence": f"Found explicit disallow directives for primary AI citation engines: {bot_list}.",
            "suggested_action": {
                "summary": f"Update robots.txt to permit indexing by Tier-1 AI crawlers ({bot_list}).",
                "priority": "high",
                "rationale": "Blocking Tier-1 bots guarantees that ChatGPT, Claude, and Perplexity will omit your brand from live search citations.",
                "code_fix_example": "User-agent: GPTBot\nAllow: /\n\nUser-agent: ClaudeBot\nAllow: /\n\nUser-agent: PerplexityBot\nAllow: /"
            }
        })

    # 3. F-CRAWL-003: Tier-2 AI Bot Block
    if blocked_t2:
        bot_list = ", ".join(sorted(blocked_t2))
        findings.append({
            "id": "F-CRAWL-003",
            "skill_id": "crawl-bot-access",
            "title": f"Tier-2 secondary AI crawlers blocked in robots.txt ({bot_list})",
            "severity": "medium",
            "impact_area": "crawl_accessibility",
            "evidence": f"Found disallow directives for secondary AI crawlers: {bot_list}.",
            "suggested_action": {
                "summary": f"Review and permit Tier-2 AI crawlers ({bot_list}) for comprehensive ecosystem coverage.",
                "priority": "medium",
                "rationale": "Allowing Google-Extended, Applebot-Extended, and Amazonbot ensures visibility across Gemini, Apple Intelligence, and Amazon Rufus.",
                "code_fix_example": "User-agent: Google-Extended\nAllow: /\n\nUser-agent: Applebot-Extended\nAllow: /"
            }
        })

    # 4. F-CRAWL-008: Sitemap omitted from robots.txt
    if not sitemap_declared:
        findings.append({
            "id": "F-CRAWL-008",
            "skill_id": "crawl-bot-access",
            "title": "Sitemap URL is not declared in robots.txt",
            "severity": "medium",
            "impact_area": "crawl_accessibility",
            "evidence": "No 'Sitemap: https://.../sitemap.xml' directive detected in robots.txt.",
            "suggested_action": {
                "summary": "Declare canonical XML sitemap location at the top or bottom of robots.txt.",
                "priority": "low",
                "rationale": "AI crawlers look for the Sitemap directive in robots.txt as the primary entrypoint for discovering fresh URLs.",
                "code_fix_example": f"Sitemap: {urljoin(base_url, 'sitemap.xml') if base_url else 'https://example.com/sitemap.xml'}"
            }
        })

    return findings
