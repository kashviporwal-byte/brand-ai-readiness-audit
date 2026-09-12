"""
Subskill 1.4: /llms.txt and /llms-full.txt AI Discovery Auditor
Audits the adoption of the emerging llms.txt standard:
- Missing /llms.txt (F-CRAWL-011)
- Missing /llms-full.txt (F-CRAWL-012)
Rule IDs: F-CRAWL-011, F-CRAWL-012
"""


def check_llms_txt(llms_txt_content, filename="llms.txt", status_code=200):
    findings = []
    fid = "F-CRAWL-011" if filename == "llms.txt" else "F-CRAWL-012"
    severity = "low"

    if status_code != 200 or llms_txt_content is None:
        findings.append({
            "id": fid,
            "skill_id": "crawl-bot-access",
            "title": f"Missing modern AI discovery manifest (/{filename})",
            "severity": severity,
            "impact_area": "crawl_accessibility",
            "evidence": f"HTTP GET /{filename} returned status {status_code}. The site has not published an LLM manifest.",
            "suggested_action": {
                "summary": f"Publish a standardized markdown /{filename} file at the domain root.",
                "priority": "low",
                "rationale": "The /llms.txt standard provides a clean, token-efficient summary map for AI models without HTML boilerplate.",
                "code_fix_example": (
                    f"# Brand Name\n\n"
                    f"> Short 2-sentence description of the platform.\n\n"
                    f"## Documentation\n"
                    f"- [Quickstart](https://example.com/docs): Developer setup guide.\n"
                    f"- [API Reference](https://example.com/api): Core REST API spec."
                )
            }
        })
        return findings

    content = llms_txt_content.strip()
    if not content or len(content) < 20:
        findings.append({
            "id": fid,
            "skill_id": "crawl-bot-access",
            "title": f"Invalid or empty /{filename} content",
            "severity": "medium",
            "impact_area": "crawl_accessibility",
            "evidence": f"File /{filename} exists but content length is {len(content)} bytes (insufficient substance).",
            "suggested_action": {
                "summary": f"Populate /{filename} with concise markdown summaries and links to primary pages.",
                "priority": "low",
                "rationale": "Empty manifest files confuse automated AI aggregators.",
                "code_fix_example": "# Platform Name\n> Concise summary.\n- [Docs](/docs)"
            }
        })
    elif not content.startswith("#"):
        findings.append({
            "id": fid,
            "skill_id": "crawl-bot-access",
            "title": f"Non-standard /{filename} formatting (missing H1 header)",
            "severity": "low",
            "impact_area": "crawl_accessibility",
            "evidence": f"File /{filename} does not begin with a standard markdown header ('# Title'). First line: '{content.splitlines()[0][:50]}'.",
            "suggested_action": {
                "summary": f"Format /{filename} as clean Markdown starting with a primary '# Title' heading.",
                "priority": "low",
                "rationale": "The llms.txt standard specification mandates valid Markdown starting with an H1 brand title.",
                "code_fix_example": "# Brand Title\n> Product summary."
            }
        })

    return findings
