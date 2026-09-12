# Brand AI-Readiness Audit Marketplace

A production-grade, modular Agent Skill Marketplace built for the **Adobe University Hackathon 2026 Round 3**.

This marketplace adheres strictly to the [`agentskills.io`](https://agentskills.io) specification. It enables any autonomous AI agent to audit **any unseen website** automatically, identifying defects that hurt **AI Discoverability** (getting crawled, understood, and cited by ChatGPT, Claude, Perplexity, Copilot, SearchGPT) and **On-Site Engagement** (retaining visitors referred by AI citations).

---

## Architecture Overview

The marketplace is decomposed into **5 specialized domain skills** composed cleanly by **1 master entrypoint skill**:

1. **`audit-orchestrator`** *(Entrypoint)*: Coordinates the polite, single-pass crawl respecting `robots.txt`, fans out in-memory payloads to domain skills in parallel, applies deterministic deduplication and severity scoring, and emits the final JSON audit report.
2. **`crawl-bot-access`**: Audits AI user-agent directives in `robots.txt`, `X-Robots-Tag` headers (`noai`, `noindex`), sitemap availability, and `/llms.txt` adoption.
3. **`render-extraction-audit`**: Audits client-side JS hydration gaps (SPA blank shells), facts locked in non-text media (missing `alt`, canvas, video/audio transcripts), and semantic HTML hierarchy.
4. **`entity-semantics-audit`**: Validates Schema.org JSON-LD, entity disambiguation via `sameAs` knowledge graph links, quotable definition sentences, and locale/audience grounding.
5. **`freshness-corroboration`**: Audits temporal metadata, 2-source cross-web claim corroboration (preventing directory false positives), and information density (Appendix F summarization resilience).
6. **`engagement-ux-audit`**: Audits heading anchor IDs (`#section-id`) for AI deep-link citations, above-the-fold 3-second value clarity, intrusive popup friction, and readability ease.

---

## Directory Layout

```text
brand-ai-readiness-audit/
├── marketplace.json                         <- Contest manifest (declares skills + entrypoint)
├── README.md                                <- System architecture & usage documentation
└── skills/
    ├── audit-orchestrator/                  <- [ENTRYPOINT SKILL]
    │   ├── SKILL.md
    │   ├── scripts/
    │   └── references/
    ├── crawl-bot-access/
    │   ├── SKILL.md
    │   ├── scripts/
    │   └── references/
    ├── render-extraction-audit/             <- [MACHINE READABILITY SKILL]
    │   ├── SKILL.md
    │   ├── scripts/
    │   └── references/
    ├── entity-semantics-audit/
    │   ├── SKILL.md
    │   ├── scripts/
    │   └── references/
    ├── freshness-corroboration/
    │   ├── SKILL.md
    │   ├── scripts/
    │   └── references/
    └── engagement-ux-audit/
        ├── SKILL.md
        ├── scripts/
        └── references/
```

---

## Running the Audit

### Mode 1: Standard Single-Page Audit (Default)
Fast, polite audit of a specific landing page or target URL:
```bash
python skills/audit-orchestrator/scripts/orchestrate_audit.py https://example.com --output report.json
```

### Mode 2: Multi-Page Site-Wide Audit (Sitemap Traversal)
Site-wide audit discovering and analyzing key high-intent pages (`/pricing`, `/docs`, `/about`) via `sitemap.xml`:
```bash
python skills/audit-orchestrator/scripts/orchestrate_audit.py https://example.com --multi-page --max-pages 3 --output report.json
```

### Mode 3: Offline / Local HTML File Audit
Audit local `.html` files without network dependencies:
```bash
python skills/audit-orchestrator/scripts/orchestrate_audit.py ./local_page.html --output report.json
```

Outputs the official `report.json` conforming strictly to the contest `report_schema.json` in seconds without external dependencies.

---

## Testing & Verification

Run the comprehensive offline unit test suite covering all 5 domain skills, orchestrator functions, and regression probes:

```bash
python tests/test_all.py
```

---

## Safety Guardrails & Design Choices

1. **Strict Read-Only Operations**: All network interactions use read-only HTTP GET requests. No write, mutation, or state-changing requests are performed.
2. **Robots.txt Gating**: Secondary multi-page discovery and secondary User-Agent fetches strictly check `robots.txt` rules using `urllib.robotparser`.
3. **UA-Cloaking Verification**: `render-extraction-audit` issues one secondary GET request under `User-Agent: GPTBot/1.0` (robots.txt-gated) to detect bot-blocking or differential payload rendering (`F-REND-014`).
4. **Wall-Clock Safety Deadline**: Orchestration caps cumulative execution at a 240-second (4-minute) wall-clock budget to guarantee `< 5 minute` completion on slow target domains.
