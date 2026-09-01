# Schema.org Structured Data Requirements for AI Discoverability

This reference defines which Schema.org entity types, required fields, and
validation rules are applied by the `entity-semantics-audit` skill.

---

## 1. Why Schema.org JSON-LD Matters to AI

Modern AI knowledge graph systems (Google Knowledge Graph, Bing Satori, ChatGPT
Browse, Perplexity) ingest Schema.org JSON-LD as **the primary structured-data
input** when building entity cards and factual answer banks.

```
Raw HTML Page
      │
      ├── <script type="application/ld+json"> ──→ Knowledge Graph Ingest
      │         (Organization, Product, FAQ)       (High-trust, machine-readable)
      │
      └── Visible Body Text ──────────────────→ NLP Extraction
                                                  (Lower-trust, prone to hallucination)
```

JSON-LD is preferred because it is:
- **Isolated**: Not mixed with display markup; impossible to misparse.
- **Typed**: `@type` provides unambiguous entity classification.
- **Linked**: `sameAs` connects to external KGs for disambiguation.

---

## 2. Core Entity Types — Required on Brand Pages

| @type                 | Required On         | Critical Fields                        |
|:----------------------|:--------------------|:---------------------------------------|
| `Organization`        | Homepage            | name, description, url, logo, sameAs   |
| `Corporation`         | Homepage            | name, description, url, logo, sameAs   |
| `LocalBusiness`       | Location pages      | name, description, url, address        |
| `Brand`               | Product pages       | name, description, url                 |
| `Product`             | Product pages       | name, description, offers              |
| `Service`             | Service pages       | name, description, provider            |
| `SoftwareApplication` | App / product pages | name, description, operatingSystem     |
| `WebApplication`      | SaaS pages          | name, description, applicationCategory |

---

## 3. High-Value Optional Fields (Increase AI Citation Confidence)

These fields are not required but significantly improve knowledge graph richness:

| Field             | @type Context       | AI Benefit                                             |
|:------------------|:--------------------|:-------------------------------------------------------|
| `sameAs`          | Organization        | Entity disambiguation; prevents brand confusion        |
| `founder`         | Organization        | Answers "Who founded X?" accurately                    |
| `foundingDate`    | Organization        | Answers "When was X founded?"                          |
| `numberOfEmployees` | Organization      | Answers size / scale queries                           |
| `award`           | Organization        | Surfaces in "best X" AI answers                        |
| `aggregateRating` | Product / Service   | Used in AI answer snippets for social proof            |
| `review`          | Product / Service   | Sentiment grounding for AI answer confidence           |
| `faqPage`         | WebPage             | Directly feeds ChatGPT / Perplexity FAQ answer boxes   |

---

## 4. JSON-LD Validation Rules

### 4.1 Syntax Requirements
- All blocks must parse as valid JSON (no trailing commas, unquoted keys, comments).
- `@context` must be `"https://schema.org"` (not `"http://schema.org"` — avoid HTTP).
- `@type` must be a valid Schema.org type string or array of strings.

### 4.2 Common Malformation Patterns (F-ENT-003 Triggers)
```json
// ❌ Trailing comma
{ "@type": "Organization", "name": "Acme", }

// ❌ JavaScript comment (JSON does not support comments)
{ /* @type */ "@type": "Organization" }

// ❌ Single-quoted strings (JSON requires double quotes)
{ '@type': 'Organization', 'name': 'Acme' }
```

### 4.3 @graph Pattern (Correct Multi-Schema Block)
```json
{
  "@context": "https://schema.org",
  "@graph": [
    { "@type": "Organization", "name": "Acme Corp", "url": "https://acme.com" },
    { "@type": "WebSite", "url": "https://acme.com", "name": "Acme" }
  ]
}
```

---

## 5. Minimum Viable Organization Schema (Copy-Paste Template)

```json
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Acme Corp",
  "legalName": "Acme Corporation Inc.",
  "description": "Acme Corp automates enterprise workflows for Fortune 500 teams, reducing operational latency by 70%.",
  "url": "https://acme.com",
  "logo": {
    "@type": "ImageObject",
    "url": "https://acme.com/logo.png",
    "width": 600,
    "height": 60
  },
  "foundingDate": "2018",
  "numberOfEmployees": {
    "@type": "QuantitativeValue",
    "value": 250
  },
  "sameAs": [
    "https://www.wikidata.org/wiki/Q12345",
    "https://en.wikipedia.org/wiki/Acme_Corp",
    "https://www.crunchbase.com/organization/acme-corp",
    "https://www.linkedin.com/company/acme-corp",
    "https://github.com/acme-corp"
  ],
  "areaServed": ["US", "GB", "CA", "AU"],
  "inLanguage": "en"
}
</script>
```

---

## 6. Testing & Validation Tools

| Tool | URL | Purpose |
|:-----|:----|:--------|
| Schema.org Validator | https://validator.schema.org/ | Validate JSON-LD syntax and completeness |
| Google Rich Results Test | https://search.google.com/test/rich-results | Preview how Google interprets schemas |
| Bing Markup Validator | https://www.bing.com/webmaster/tools | Bing-specific structured data validation |
