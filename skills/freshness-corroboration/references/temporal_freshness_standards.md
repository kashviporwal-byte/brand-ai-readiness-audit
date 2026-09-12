# Temporal Freshness Standards for AI Discoverability

This reference defines the temporal metadata standards, staleness thresholds, and
copyright drift detection rules applied by the `freshness-corroboration` skill
(Subskill 4.1: `temporal_freshness_checker.py`).

---

## 1. Why Temporal Freshness Matters to AI

Modern AI search and retrieval systems apply **temporal decay weighting** when ranking
and citing content. A page without explicit date signals receives a lower trust score
compared to a page with a recent `dateModified` timestamp.

```
Raw HTML Page
      │
      ├── <meta name="article:modified_time"> ──→ Temporal Trust Signal (High)
      │
      ├── JSON-LD dateModified ────────────────→ Knowledge Graph Timestamp (High)
      │
      ├── <time datetime="2025-01-15"> ────────→ Inline Temporal Grounding (Medium)
      │
      └── Copyright Footer "© 2021" ───────────→ Freshness Decay Signal (Low / Negative)
```

AI assistants such as ChatGPT Browse, Perplexity, and Bing Copilot explicitly
deprioritize pages that:
- Lack any machine-readable date signals.
- Have `dateModified` older than 18 months for technical/product documentation.
- Carry footer copyright notices 2+ years behind the current calendar year.

---

## 2. Temporal Metadata Hierarchy (Priority Order)

The `temporal_freshness_checker.py` extracts timestamps in the following priority order,
from highest to lowest machine-readable trust:

| Priority | Source | Extraction Method | Coverage |
| :---: | :--- | :--- | :--- |
| **1** | JSON-LD `dateModified` | `<script type="application/ld+json">` | Best: typed, schema-linked |
| **2** | JSON-LD `datePublished` | `<script type="application/ld+json">` | Good: stable publication anchor |
| **3** | JSON-LD `uploadDate` | `<script type="application/ld+json">` (VideoObject) | Video content |
| **4** | `<meta>` `article:modified_time` | Open Graph / Facebook meta | Editorial CMS pages |
| **5** | `<meta>` `article:published_time` | Open Graph / Facebook meta | Editorial CMS pages |
| **6** | `<meta>` `og:updated_time` | Open Graph extension | Social media pages |
| **7** | `<meta>` `DC.date` | Dublin Core metadata | Academic / institutional pages |
| **8** | `<meta name="date">` | Generic HTML meta | Basic CMS pages |
| **9** | `<meta name="last-modified">` | Generic HTML meta | Legacy pages |
| **10** | `<time datetime="...">` | HTML5 semantic time element | Inline article dates |

---

## 3. ISO 8601 Validation Rules

All timestamp values are validated against the ISO 8601 standard.

### Accepted Formats:
- Full datetime: `2025-06-15T14:30:00Z`
- Full datetime with offset: `2025-06-15T14:30:00+05:30`
- Date only: `2025-06-15`
- Year-month: `2025-06`

### Rejection Triggers (→ `F-FRSH-003`):
- **Non-ISO human-readable strings**: `"June 15, 2025"`, `"15/06/2025"`, `"2025.06.15"`
- **Future-dated timestamps**: Date more than 24 hours ahead of crawl time (clock skew allowed).
- **Year-only strings**: `"2025"` alone without month is insufficient for freshness scoring.
- **Unix epoch integers**: `1718452200` without a string wrapper is not schema-compliant.

---

## 4. Staleness Thresholds by Page Type

AI retrieval systems apply different freshness tolerances based on content type:

| Page Type | Acceptable `dateModified` Age | Severity if Missing |
| :--- | :--- | :--- |
| Product / Pricing page | <= 6 months | `High` (F-FRSH-001) |
| Technical documentation | <= 12 months | `High` (F-FRSH-001) |
| Blog / News article | <= 24 months | `Medium` |
| About / Company page | <= 36 months | `Medium` |
| Legal / Terms page | Any (evergreen) | `Low` |

---

## 5. Copyright Year Drift Detection

### Detection Patterns (Regex):
The checker scans footer regions and visible text for copyright signals:

```
© 2021                          ← Direct year: gap = currentYear - 2021
Copyright 2018-2022             ← Range: end year = 2022
(c) 2020 BrandName              ← ASCII copyright: gap = currentYear - 2020
Copyright (C) 2019 Corp         ← Verbose form
```

### Staleness Thresholds:
| Gap (Current Year − Copyright Year) | Severity | Finding |
| :--- | :--- | :--- |
| >= 2 years | `Medium` | F-FRSH-002 |
| >= 4 years | `High` | F-FRSH-002 (escalated) |
| 0 – 1 years | Pass | No finding |

### Fix Example:
```html
<!-- BEFORE (stale): -->
<footer>© 2021 AcmeCorp. All rights reserved.</footer>

<!-- AFTER (dynamic): -->
<footer>© <span id="copyright-year"></span> AcmeCorp. All rights reserved.</footer>
<script>document.getElementById('copyright-year').textContent = new Date().getFullYear();</script>
```

---

## 6. AI Temporal Decay Curve (Qualitative Model)

```
Citation Confidence
     │
100% ├────────────────────────────────╮
     │  Fresh (< 3 months)            │ Peak zone
 80% │                                ╰────────────────╮
     │  Recent (3–12 months)                           │ Acceptable
 60% │                                                 ╰──────────────╮
     │  Stale (12–24 months)                                          │ Discounted
 40% │                                                                ╰────────────╮
     │  Very Stale (24–36 months)                                                  │ Unlikely to cite
 20% │                                                                             ╰──────╮
     │  Expired (> 36 months, no dateModified)                                           │ Avoided
  0% ├────────────────────────────────────────────────────────────────────────────────────┘
     └────────────────────────────────────────────────── Time →
```
