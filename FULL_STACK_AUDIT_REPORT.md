# Full-Stack Brand AI-Readiness Benchmark Audit Report

**Generated At**: 2026-09-04T10:46:10.361973+00:00  
**Engine Version**: `1.0.0-production`  
**Execution Environment**: Pure Python Standard Library (Zero External Dependencies)

---

## Executive Summary

This report documents the empirical benchmark results of the **Brand AI-Readiness Audit Engine** across 5 representative web architectures (SaaS Platform, Sphinx Documentation, Modern Web App SPA, Legacy Forum, and Global Knowledge Base).

All rule IDs (`F-CRAWL-xxx`, `F-REND-xxx`, `F-ENT-xxx`, `F-ENG-xxx`, `F-FRSH-xxx`) in this document are generated verbatim by the production domain skills.

---

## Benchmark Audit Summary

| Target Site | AI Score | Total Issues | Critical | High | Medium | Low | Audit Time | Key Driver |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `https://stripe.com` | **49/100** | 12 | 0 | 3 | 4 | 5 | 26.781s | Score 49/100: Driven primarily by 5 finding(s) in render-extraction-audit, 3 finding(s) in freshness-corroboration. |
| `https://docs.python.org/3/` | **31/100** | 12 | 0 | 5 | 4 | 3 | 13.394s | Score 31/100: Driven primarily by 4 finding(s) in entity-semantics-audit, 3 finding(s) in crawl-bot-access. |
| `https://react.dev` | **1/100** | 18 | 0 | 7 | 6 | 5 | 6.252s | Score 1/100: Driven primarily by 5 finding(s) in render-extraction-audit, 4 finding(s) in freshness-corroboration. |
| `https://news.ycombinator.com` | **0/100** | 17 | 0 | 8 | 5 | 4 | 14.306s | Score 0/100: Driven primarily by 5 finding(s) in crawl-bot-access, 4 finding(s) in entity-semantics-audit. |
| `https://wikipedia.org` | **30/100** | 13 | 0 | 5 | 4 | 4 | 12.807s | Score 30/100: Driven primarily by 3 finding(s) in entity-semantics-audit, 3 finding(s) in freshness-corroboration. |

---

## Detailed Benchmark Findings by Target Site

### Target: https://stripe.com
- **Overall AI Score**: 49/100
- **Primary Diagnosis**: Score 49/100: Driven primarily by 5 finding(s) in render-extraction-audit, 3 finding(s) in freshness-corroboration.
- **Audit Duration**: 26.781 seconds

| Rule ID | Severity | Title | Evidence Preview |
| :--- | :---: | :--- | :--- |
| `F-ENG-001` | `HIGH` | Major section headings lack anchor IDs for AI deep-link citations | Audited 30 content section headings (H2/H3); 19 (63.3%) lack an HTML 'id' attrib... |
| `F-REND-003` | `HIGH` | Critical facts and diagrams trapped in images with missing or low-quality alt text | Audited 30 informational images; 26/30 (86.7%) have defective alt attributes: 26... |
| `F-FRSH-001` | `HIGH` | Missing datePublished / dateModified temporal metadata | No machine-readable publication or modification date found on https://stripe.com... |
| `F-ENG-004` | `MEDIUM` | Initial viewport lacks a visible, prominent Call-To-Action (CTA) | Found 0 actionable Call-To-Action elements (e.g. 'Start Free Trial', 'Book Demo'... |
| `F-REND-004` | `MEDIUM` | Interactive <canvas> data visualizations lack machine-readable text fallbacks | Found 1 <canvas> elements; 1 lack aria-label, aria-describedby, or fallback DOM ... |

### Target: https://docs.python.org/3/
- **Overall AI Score**: 31/100
- **Primary Diagnosis**: Score 31/100: Driven primarily by 4 finding(s) in entity-semantics-audit, 3 finding(s) in crawl-bot-access.
- **Audit Duration**: 13.394 seconds

| Rule ID | Severity | Title | Evidence Preview |
| :--- | :---: | :--- | :--- |
| `F-ENT-001` | `HIGH` | Missing core Schema.org entity markup (Organization or Product) | No <script type="application/ld+json"> blocks found on the page. The page has ze... |
| `F-ENT-004` | `HIGH` | Brand entity completely lacks sameAs knowledge graph disambiguation links | No sameAs property found in any JSON-LD block. No outbound hyperlinks to authori... |
| `F-ENT-006` | `HIGH` | No clear quotable entity definition sentence found in top 200 words | Scanned first 0 visible words and meta description (present). No clear 'X is a/a... |
| `F-FRSH-001` | `HIGH` | Missing datePublished / dateModified temporal metadata | No machine-readable publication or modification date found on https://docs.pytho... |
| `F-ENG-001` | `HIGH` | Major section headings lack anchor IDs for AI deep-link citations | Audited 5 content section headings (H2/H3); 5 (100.0%) lack an HTML 'id' attribu... |

### Target: https://react.dev
- **Overall AI Score**: 1/100
- **Primary Diagnosis**: Score 1/100: Driven primarily by 5 finding(s) in render-extraction-audit, 4 finding(s) in freshness-corroboration.
- **Audit Duration**: 6.252 seconds

| Rule ID | Severity | Title | Evidence Preview |
| :--- | :---: | :--- | :--- |
| `F-FRSH-001` | `HIGH` | Missing datePublished / dateModified temporal metadata | No machine-readable publication or modification date found on https://react.dev.... |
| `F-ENT-001` | `HIGH` | Missing core Schema.org entity markup (Organization or Product) | No <script type="application/ld+json"> blocks found on the page. The page has ze... |
| `F-ENT-004` | `HIGH` | Brand entity completely lacks sameAs knowledge graph disambiguation links | No sameAs property found in any JSON-LD block. No outbound hyperlinks to authori... |
| `F-ENG-001` | `HIGH` | Major section headings lack anchor IDs for AI deep-link citations | Audited 47 content section headings (H2/H3); 47 (100.0%) lack an HTML 'id' attri... |
| `F-ENG-003` | `HIGH` | Above-the-fold hero section lacks a descriptive value proposition (fails 3-second rule) | Primary hero heading ('React') is missing or consists of an abstract marketing s... |

### Target: https://news.ycombinator.com
- **Overall AI Score**: 0/100
- **Primary Diagnosis**: Score 0/100: Driven primarily by 5 finding(s) in crawl-bot-access, 4 finding(s) in entity-semantics-audit.
- **Audit Duration**: 14.306 seconds

| Rule ID | Severity | Title | Evidence Preview |
| :--- | :---: | :--- | :--- |
| `F-ENT-001` | `HIGH` | Missing core Schema.org entity markup (Organization or Product) | No <script type="application/ld+json"> blocks found on the page. The page has ze... |
| `F-ENT-004` | `HIGH` | Brand entity completely lacks sameAs knowledge graph disambiguation links | No sameAs property found in any JSON-LD block. No outbound hyperlinks to authori... |
| `F-ENT-006` | `HIGH` | No clear quotable entity definition sentence found in top 200 words | Scanned first 200 visible words and meta description (absent). No clear 'X is a/... |
| `F-FRSH-001` | `HIGH` | Missing datePublished / dateModified temporal metadata | No machine-readable publication or modification date found on https://news.ycomb... |
| `F-ENG-003` | `HIGH` | Above-the-fold hero section lacks a descriptive value proposition (fails 3-second rule) | Primary hero heading (None detected) is missing or consists of an abstract marke... |

### Target: https://wikipedia.org
- **Overall AI Score**: 30/100
- **Primary Diagnosis**: Score 30/100: Driven primarily by 3 finding(s) in entity-semantics-audit, 3 finding(s) in freshness-corroboration.
- **Audit Duration**: 12.807 seconds

| Rule ID | Severity | Title | Evidence Preview |
| :--- | :---: | :--- | :--- |
| `F-ENT-001` | `HIGH` | Missing core Schema.org entity markup (Organization or Product) | No <script type="application/ld+json"> blocks found on the page. The page has ze... |
| `F-ENG-003` | `HIGH` | Above-the-fold hero section lacks a descriptive value proposition (fails 3-second rule) | Primary hero heading ('Wikipedia') is missing or consists of an abstract marketi... |
| `F-FRSH-001` | `HIGH` | Missing datePublished / dateModified temporal metadata | No machine-readable publication or modification date found on https://www.wikipe... |
| `F-REND-003` | `HIGH` | Critical facts and diagrams trapped in images with missing or low-quality alt text | Audited 1 informational images; 1/1 (100.0%) have defective alt attributes: 1 im... |
| `F-CRAWL-007` | `HIGH` | XML sitemap is unreachable (HTTP 404 Not Found) | GET https://en.wikipedia.org/w/rest.php/site/v1/sitemap/0 returned status 403. N... |

