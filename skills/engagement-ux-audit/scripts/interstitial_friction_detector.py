"""
Subskill 5.3: Intrusive Friction & Interstitial Detector
Detects blocking modals, unclosable newsletter overlays, full-screen popups,
and aggressive cookie walls that cause instant bounce-backs for AI-referred users.
Includes a self-healing DOM tag stack that handles unclosed tags (<p>, <li>)
inside hidden containers without desynchronizing the detector for later content.
Rule ID: F-ENG-005
"""

import re
from html.parser import HTMLParser


MODAL_SINGLE_KEYWORDS = frozenset({
    "modal", "popup", "overlay", "interstitial", "paywall", "lightbox"
})

MODAL_COMPOUND_PATTERNS = re.compile(
    r"\b(cookie-wall|email-capture|gate-wall|newsletter-popup|paywall-gate|subscribe-gate)\b",
    re.IGNORECASE
)

VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr"
})


class InterstitialParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocking_elements = []
        self.has_dialog_role = False
        self.inline_blocking_styles = []
        self.tag_stack = []  # list of dicts: {"tag": str, "is_hidden": bool}

    @property
    def is_in_hidden_ancestor(self):
        return any(entry["is_hidden"] for entry in self.tag_stack)

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        attr_dict = {k.lower(): (v or "").strip() for k, v in attrs}

        cls = attr_dict.get("class", "").lower()
        elem_id = attr_dict.get("id", "").lower()
        role = attr_dict.get("role", "").lower()
        style = attr_dict.get("style", "").lower().replace(" ", "")
        is_void = tag_lower in VOID_TAGS

        # Check if element itself is statically hidden on initial load
        # Note: Per HTML5 spec, <dialog> is hidden by default unless it carries the boolean 'open' attribute.
        is_self_hidden = (
            "display:none" in style or
            "visibility:hidden" in style or
            "hidden" in attr_dict or
            attr_dict.get("aria-hidden") == "true" or
            (tag_lower == "dialog" and "open" not in attr_dict)
        )

        in_hidden_ancestor = self.is_in_hidden_ancestor

        # Push non-void elements to tag stack with their hidden status
        if not is_void:
            self.tag_stack.append({
                "tag": tag_lower,
                "is_hidden": is_self_hidden
            })

        # If inside a hidden ancestor or element itself is hidden, it's dormant on load
        if in_hidden_ancestor or is_self_hidden:
            return

        # Element is visible on load!
        if role in ("dialog", "alertdialog"):
            self.has_dialog_role = True

        tokens = set(re.split(r"[-_\s]+", f"{cls} {elem_id}"))
        matched_single = tokens & MODAL_SINGLE_KEYWORDS
        matched_compound = MODAL_COMPOUND_PATTERNS.findall(f"{cls} {elem_id}")
        all_matches = list(matched_single) + matched_compound

        if all_matches:
            self.blocking_elements.append({
                "tag": tag_lower,
                "id": elem_id,
                "class": cls,
                "matched": all_matches
            })

        if "position:fixed" in style:
            if any(k in style for k in ("inset:0", "top:0;left:0", "width:100vw", "height:100vh")):
                if "z-index" in style:
                    self.inline_blocking_styles.append(f"{tag_lower} style=\'{style[:40]}\'")

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower in VOID_TAGS:
            return

        # Self-healing backwards pop: if unclosed tags (<p>, <li>) existed inside a container,
        # closing the container closes all unclosed children up to and including the matching tag.
        tags_on_stack = [entry["tag"] for entry in self.tag_stack]
        if tag_lower in tags_on_stack:
            while self.tag_stack:
                popped = self.tag_stack.pop()
                if popped["tag"] == tag_lower:
                    break


def check_interstitial_friction(raw_html, page_url=""):
    findings = []
    if not raw_html:
        return findings

    # Check for immediate intrusive modal triggers in script blocks
    script_triggers = []
    script_patterns = [
        re.compile(r"\b(?:showModal|openPopup|displayNewsletter|triggerPaywall|showCookieWall)\s*\(", re.IGNORECASE),
        re.compile(r"\bwindow\.onload\s*=\s*function[^{]*{[^}]*(?:modal|popup|overlay)\.style\.display\s*=\s*['\"]block", re.IGNORECASE)
    ]
    for pattern in script_patterns:
        if pattern.search(raw_html):
            script_triggers.append("Auto-executing modal script on window.onload")

    parser = InterstitialParser()
    try:
        parser.feed(raw_html)
    except Exception:
        pass

    is_intrusive = bool(script_triggers) or len(parser.blocking_elements) >= 2 or bool(parser.inline_blocking_styles)

    if is_intrusive:
        details = []
        if script_triggers:
            details.append(f"Script triggers: {script_triggers[0]}")
        if parser.blocking_elements:
            sample_el = parser.blocking_elements[0]
            details.append(f"Overlay container: <{sample_el['tag']} class='{sample_el['class']}'> (matched {sample_el['matched']})")
        if parser.inline_blocking_styles:
            details.append(f"Full-screen fixed viewport styles: {len(parser.inline_blocking_styles)} element(s)")

        evidence_str = "; ".join(details)
        findings.append({
            "id": "F-ENG-005",
            "skill_id": "engagement-ux-audit",
            "title": "Intrusive blocking modal, overlay, or newsletter paywall obstructs arrival",
            "severity": "high",
            "impact_area": "on_site_engagement",
            "evidence": (
                f"Detected intrusive overlay friction patterns on initial page load: {evidence_str}. "
                f"Visitors arriving from AI citations to read a specific fact are blocked by modal barriers."
            ),
            "suggested_action": {
                "summary": "Defer promotional overlays to exit-intent and provide unblocked access to page content.",
                "priority": "high",
                "rationale": (
                    "Users referred by AI assistant citations arrive with high intent to verify a single answer. "
                    "Interrupting them immediately with forced email captures or blocking dialogs causes instant bounce-backs."
                ),
                "code_fix_example": (
                    "// Defer modal trigger to exit-intent or 60s reading duration:\n"
                    "document.addEventListener('mouseleave', (e) => {\n"
                    "  if (e.clientY <= 0 && !hasDismissedPopup) showExitIntentModal();\n"
                    "});"
                )
            }
        })

    return findings
