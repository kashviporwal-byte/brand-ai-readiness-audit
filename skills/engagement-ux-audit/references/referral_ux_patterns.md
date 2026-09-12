# AI Referral UX & Visitor Orientation Patterns

This document details the user experience principles and failure mechanisms that dictate whether visitors referred by AI assistants (ChatGPT, Perplexity, Claude, Gemini, SearchGPT) engage with a website or immediately bounce back to the AI interface.

---

## 1. The Anatomy of an AI Referral Jump

When an AI assistant answers a user query, it synthesizes factual claims from multiple web sources and embeds clickable citation links. Modern assistants increasingly generate **URL fragment deep-links**:

```text
https://example.com/platform-docs#sub-millisecond-latency
```

### The Expectation
When a user clicks that link, they expect the browser to jump directly to the paragraph, benchmark table, or heading that proves the AI's statement.

### The Friction (F-ENG-001: Missing Heading Anchor IDs)
If the website's headings (`<h2>`, `<h3>`) do not have HTML `id` attributes:
1. The browser cannot resolve the fragment `#sub-millisecond-latency`.
2. The browser dumps the visitor at the very top of a 4,000-word document.
3. The visitor cannot immediately find the cited claim, concludes the AI hallucinated or the link is irrelevant, and clicks "Back" within 2 seconds.

---

## 2. The 3-Second Orientation Rule (Above-The-Fold Value Clarity)

Visitors arriving from AI citations have **high specific intent** but **low brand familiarity**. Unlike direct organic visitors who navigated from the homepage, an AI-referred visitor may have never heard of the brand before.

### Critical Elements Required in the Initial Viewport:
1. **Descriptive Entity Headline**: Clearly states what the product/service is without cryptic marketing metaphors.
2. **Substantiating Subhead**: Explains who it is for and its primary value proposition.
3. **Prominent Call-To-Action (CTA)**: A visible, clickable conversion element (`Start Free Trial`, `Read Documentation`, `Get a Demo`).

### Anti-Patterns (F-ENG-003 & F-ENG-004):
- Vague slogans ("Unleashing the Future of Tomorrow") that convey zero factual substance.
- Giant decorative video or image backgrounds pushing all readable text below 1000px.
- Complete absence of an above-the-fold CTA button.

---

## 3. Interstitial Friction & Paywall Bounce Drivers (F-ENG-005)

When an AI assistant quotes a website, the visitor clicks to verify a specific sentence. 

### Why Modals Cause Instant Bounces:
1. **Immediate Full-Screen Newsletter Overlays**: Popping up a "Subscribe for 10% off" or "Join our newsletter" modal before the user has read a single sentence triggers instant bounce-backs.
2. **Unclosable Cookie/Tracking Walls**: Forcing extensive cookie choices without a one-click "Accept All" or "Dismiss" button blocks the user from viewing the cited answer.
3. **Forced App Download Banners**: Interstitial banners that obstruct the reading viewport on mobile or desktop devices.

---

## 4. Remediation Best Practices

1. **Automate Heading Slugs**: Ensure CMS templates automatically generate URL-safe `id` attributes from heading text (e.g. `<h2>Enterprise Security</h2>` -> `<h2 id="enterprise-security">`).
2. **Anchor Link Affordance**: Provide a hover anchor link (`#`) next to all section headings so visitors and AI assistants can easily copy deep citation links.
3. **Exit-Intent Only for Modals**: Never trigger modal overlays on page load (`window.onload`). Defer promotional modals to exit intent or after at least 60 seconds of active reading.
