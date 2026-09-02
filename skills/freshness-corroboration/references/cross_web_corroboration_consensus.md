# Cross-Web Claim Corroboration & 2-Source Consensus Rule (Appendix D)

This reference defines the entity claim extraction taxonomy, the 2-source consensus
verification protocol, and false-positive elimination rules applied by the
`freshness-corroboration` skill (Subskill 4.2: `cross_web_corroborator.py`).

---

## 1. Why Cross-Web Corroboration Matters to AI

AI language models are trained on billions of documents from across the web. When
multiple independent sources agree on a fact about a brand (founding date, leadership,
headquarters address), the model gains high confidence and cites that fact readily.

When sources conflict, AI models either:
1. **Hallucinate a reconciled answer** that may not match the brand's actual truth.
2. **Suppress the fact entirely** to avoid presenting conflicting information.
3. **Prefer the older, more frequently cited source** regardless of its accuracy.

```
Brand Website: "Founded in 2018"
        │
        ├── Wikidata: "Founded 2018"  ✓  Corroborates → AI trust HIGH
        ├── Crunchbase: "Founded 2017" ✗  Conflicts  → AI confusion RISK
        └── LinkedIn: "Founded 2018"  ✓  Corroborates → 2/3 agree: Medium finding
```

---

## 2. The 2-Source Consensus Rule (Appendix D Core Principle)

The 2-source consensus rule is the **anti-false-positive safeguard** at the heart of
Appendix D. It works as follows:

> A factual discrepancy is only escalated as an audit finding (`F-FRSH-004`) if
> **at least 2 independent external authoritative sources** corroborate a claim
> that conflicts with the brand's own on-page assertion.

A single stale directory or scraped aggregator site disagreeing with the brand page is
**NOT** sufficient to escalate — this is suppressed as an isolated false positive
(`F-FRSH-005`).

### Rationale:
- Third-party business directories (Yellow Pages, Yelp, G2, Capterra) are notoriously
  stale and often lag brand updates by 6–24 months.
- A single outdated directory entry does not represent genuine web disagreement.
- Requiring 2 independent sources dramatically reduces false positives while preserving
  true conflict detection accuracy.

---

## 3. Entity Claim Taxonomy

The corroborator extracts and validates the following claim categories from brand pages:

| Claim Category | On-Page Source Fields | Why It Matters to AI |
| :--- | :--- | :--- |
| **Organization Name** | JSON-LD `name`, `<title>`, `<h1>`, `og:site_name` | AI entity disambiguation; name collisions |
| **Founding Year** | JSON-LD `foundingDate`, visible text patterns `"founded in YYYY"` | "When was X founded?" queries |
| **Headquarters City/Country** | JSON-LD `address.addressLocality/Country`, `geo.region` meta | Location-sensitive AI routing |
| **CEO / Founder Names** | JSON-LD `founder`, `employee` with `JobTitle: CEO`, visible text | "Who leads X?" queries |
| **Pricing Tier Labels** | JSON-LD `offers`, visible text tier names ("Starter", "Pro", "Enterprise") | "How much does X cost?" queries |
| **Employee Count / Size** | JSON-LD `numberOfEmployees` | "How big is X?" queries |

---

## 4. Authoritative Reference Sources

The corroborator compares on-page claims against the following authoritative source tiers:

### Tier 1 — Highest Authority (Structured, Versioned Knowledge Graphs):
- **Wikidata** (`https://www.wikidata.org/wiki/Q*`): Multilingual, linked, versioned.
- **Wikipedia** (`https://en.wikipedia.org/wiki/*`): Editorially reviewed.
- **SEC EDGAR** (`https://www.sec.gov/cgi-bin/browse-edgar`): Official US corporate filings.

### Tier 2 — High Authority (Professional Networks & Tech Databases):
- **Crunchbase** (`https://www.crunchbase.com/organization/*`): Startup/funding data.
- **LinkedIn Company Pages** (`https://www.linkedin.com/company/*`): Headcount, HQ.
- **GitHub** (`https://github.com/<org>`): Verified open-source org metadata.

### Tier 3 — Medium Authority (Tech Review Directories — Used for False Positive Filtering):
- G2, Capterra, Trustpilot, Product Hunt — **Single-source only; NOT used for F-FRSH-004 escalation**.

---

## 5. NAP Consistency (Name, Address, Phone)

A core Local SEO and AI Entity Grounding concept: a brand's **Name, Address, and Phone**
(NAP) must be identical across all authoritative sources. Inconsistency:

1. **Confuses AI entity resolution**: Bing/Google may create duplicate entity cards.
2. **Reduces local search AI routing confidence**: Location-based queries may route incorrectly.
3. **Increases hallucination risk**: Models may blend facts from two misidentified entities.

### Common NAP Drift Patterns:
| Issue | Example | Risk |
| :--- | :--- | :--- |
| Abbreviated vs full name | `"Acme Inc"` vs `"Acme Incorporated"` | Duplicate entity cards |
| Address format mismatch | `"123 Main St"` vs `"123 Main Street, Suite 400"` | Local routing confusion |
| Phone format divergence | `"(800) 555-1234"` vs `"+1 800 555 1234"` | Voice assistant errors |
| Old address after office move | Wikidata shows old HQ 2 years after relocation | AI cites wrong location |

---

## 6. False Positive Suppression Rules

The following situations are explicitly suppressed and do NOT generate audit findings:

| Pattern | Reason for Suppression |
| :--- | :--- |
| Single stale directory disagrees with brand page | One source insufficient for 2-source consensus |
| Social media bio differs in phrasing (not facts) | Stylistic variation, not factual conflict |
| Wikipedia article is marked `[citation needed]` | Unverified claim; not authoritative source |
| Wikidata property is blank / not set | Absence of data ≠ contradictory claim |
| Brand has recent name change within 12 months | Legitimate transition; old references are expected |

---

## 7. Escalation Decision Tree

```
Extract on-page entity claim
         │
         ▼
Check Tier 1 sources (Wikidata, Wikipedia, SEC)
         │
    Conflict found?
    ┌────┴────┐
   YES       NO → PASS (no finding)
    │
    ▼
Check Tier 2 sources (Crunchbase, LinkedIn, GitHub)
         │
    Also conflicts?
    ┌────┴────┐
   YES       NO → F-FRSH-005 (low confidence, single source)
    │
    ▼
2-Source Consensus Triggered
    │
    ▼
F-FRSH-004 (high confidence multi-source factual conflict)
```
