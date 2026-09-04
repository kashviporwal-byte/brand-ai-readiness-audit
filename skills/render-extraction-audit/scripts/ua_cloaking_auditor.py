"""
Subskill 2.4: UA Cloaking & Differential Rendering Detector (Appendix C)
Detects content gating or cloaking where AI crawler User-Agents (e.g. GPTBot)
are served degraded or empty content compared to standard browser User-Agents.
Enforces permission gating via urllib.robotparser before making secondary fetches.

Rule ID: F-REND-014
"""

import re
import urllib.request
import urllib.error
import urllib.robotparser
from urllib.parse import urljoin, urlparse

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)
GPTBOT_UA = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.0; +https://openai.com/gptbot)"


def _strip_html_text(html):
    """Strips tags and returns clean visible word list."""
    if not html:
        return []
    clean = re.sub(r'<(?:head|script|style|svg|noscript|template)\b[^>]*>.*?</(?:head|script|style|svg|noscript|template)>', '', html, flags=re.IGNORECASE|re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', clean)
    return text.split()


def check_ua_cloaking(target_url, browser_html=""):
    """
    Checks for UA-based differential rendering or cloaking between standard browser UA and GPTBot UA.
    Enforces robots.txt permission gating prior to fetching under GPTBot UA.
    """
    findings = []
    if not target_url or not target_url.startswith(("http://", "https://")):
        return findings

    # Check permission via robots.txt first (Politeness & Guardrail Gate)
    parsed = urlparse(target_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}/"
    robots_url = urljoin(base_url, "robots.txt")
    rp = urllib.robotparser.RobotFileParser()
    can_fetch_gptbot = True
    try:
        req_r = urllib.request.Request(robots_url, headers={"User-Agent": BROWSER_UA})
        with urllib.request.urlopen(req_r, timeout=3.0) as resp_r:
            content = resp_r.read().decode("utf-8", errors="replace")
            rp.parse(content.splitlines())
            if not rp.can_fetch("GPTBot", target_url):
                can_fetch_gptbot = False
    except Exception:
        can_fetch_gptbot = True

    if not can_fetch_gptbot:
        # GPTBot is disallowed by robots.txt; report permission signal without making unauthorized fetch
        return findings

    # Compute baseline word count from browser HTML
    b_words = len(_strip_html_text(browser_html))
    if b_words < 50:
        return findings

    # Fetch secondary page under GPTBot User-Agent
    bot_html = ""
    try:
        req = urllib.request.Request(target_url, headers={"User-Agent": GPTBOT_UA, "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            bot_bytes = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            bot_html = bot_bytes.decode(charset, errors="replace")
    except Exception:
        # If request errors specifically for GPTBot UA (e.g. HTTP 403 Bot Block)
        findings.append({
            "id": "F-REND-014",
            "skill_id": "render-extraction-audit",
            "title": "AI Crawler User-Agent (GPTBot) is blocked or served differential error page",
            "severity": "critical",
            "impact_area": "render_extraction",
            "evidence": f"Target URL '{target_url}' returned HTTP error/block when requested with User-Agent 'GPTBot/1.0' while standard browser UA succeeded.",
            "suggested_action": {
                "summary": "Configure Web Application Firewall (WAF) or CDN bot management rules to permit legitimate AI search crawlers.",
                "priority": "high",
                "rationale": "Cloudflare or WAF User-Agent challenges targeting AI bots prevent ChatGPT and SearchGPT from retrieving brand content.",
                "code_fix_example": "# Cloudflare WAF Rule:\nAllow (http.user_agent contains \"GPTBot\")"
            }
        })
        return findings

    c_words = len(_strip_html_text(bot_html))

    # Diff word count ratio
    if b_words > 0 and c_words < b_words * 0.5:
        pct = round(100.0 * c_words / b_words)
        findings.append({
            "id": "F-REND-014",
            "skill_id": "render-extraction-audit",
            "title": f"AI Crawler User-Agent (GPTBot) received degraded/cloaked payload ({pct}% of browser content)",
            "severity": "critical",
            "impact_area": "render_extraction",
            "evidence": f"Requesting with standard browser UA yielded {b_words:,} words, whereas 'GPTBot/1.0' UA yielded only {c_words:,} words ({pct}% of full content). AI assistant retrieval will receive incomplete brand facts.",
            "suggested_action": {
                "summary": "Ensure server-side rendering logic and CDN edge workers serve identical HTML content to AI crawlers as human browsers.",
                "priority": "high",
                "rationale": "Differential rendering (cloaking) or bot-specific payload stripping causes AI models to extract truncated or misleading brand information.",
                "code_fix_example": "// Express / Next.js middleware:\nif (req.headers['user-agent'].includes('GPTBot')) {\n  return serveFullRenderedHtml(req, res);\n}"
            }
        })

    return findings
