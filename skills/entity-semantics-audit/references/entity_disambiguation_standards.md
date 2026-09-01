# Entity Disambiguation Standards for AI Knowledge Graphs

Guidelines for auditing entity disambiguation links and quotable definition
sentences to prevent brand hallucination and misidentification in AI systems.

---

## 1. Why Entity Disambiguation Matters

AI language models (ChatGPT, Claude, Perplexity, Gemini) resolve brand identities
during **knowledge graph lookup** — a pre-generation retrieval step that determines
which entity the user is asking about.

### The Brand Collision Problem
Without disambiguation, "Acme" could refer to:
- Acme Corporation (fictional ACME from Looney Tunes)
- Acme Packet (Oracle subsidiary)
- Acme Markets (US grocery chain)
- Acme Corp (your SaaS brand)

**sameAs links are the canonical signal** AI systems use to resolve this ambiguity.

---

## 2. The Three-Tier sameAs Authority Model

The `entity-semantics-audit` skill classifies `sameAs` links into three tiers
based on their trust weight in AI knowledge graph systems:

### Tier 1: Primary Knowledge Graph Anchors (Highest Trust)
These resolve entity identity with near-certainty:

| Source         | URL Pattern                               | AI Trust Level |
|:---------------|:------------------------------------------|:---------------|
| **Wikidata**   | `https://www.wikidata.org/wiki/Q{id}`     | ⭐⭐⭐⭐⭐ Critical |
| **Wikipedia**  | `https://en.wikipedia.org/wiki/{Entity}`  | ⭐⭐⭐⭐⭐ Critical |
| **DBpedia**    | `https://dbpedia.org/page/{Entity}`       | ⭐⭐⭐⭐ High      |

> **Why Wikidata is the gold standard**: Wikidata Q-items are the universal entity
> identifiers used by Google Knowledge Graph, Bing Satori, and most major AI
> knowledge base ingestion pipelines. A Wikidata entry provides a language-independent,
> persistent unique identifier for the entity.

### Tier 2: Business Registry & Directory Sources (High Trust)
These corroborate the entity's existence and sector:

| Source               | Domain                   | AI Benefit                    |
|:---------------------|:-------------------------|:------------------------------|
| Crunchbase           | `crunchbase.com`         | Funding, founding, team data  |
| Bloomberg            | `bloomberg.com`          | Financial facts               |
| SEC EDGAR            | `sec.gov`                | Public company verification   |
| OpenCorporates       | `opencorporates.com`     | Legal entity registration     |
| Dun & Bradstreet     | `dnb.com`                | DUNS number entity anchor     |

### Tier 3: Social & Community Profiles (Useful but Insufficient Alone)
These confirm presence but cannot disambiguate identity by themselves:

| Source       | AI Benefit                                    | Limitation                      |
|:-------------|:----------------------------------------------|:--------------------------------|
| LinkedIn     | Employee count, industry, description         | Many entities share similar names |
| GitHub       | Open-source project association               | Username squatting common       |
| Twitter/X    | Social presence signal                        | Low trust for disambiguation    |
| G2 / Glassdoor | Sentiment & sector confirmation             | Cannot resolve legal identity   |

---

## 3. Minimum sameAs Configuration

```json
"sameAs": [
  "https://www.wikidata.org/wiki/Q12345",           // REQUIRED: Tier-1 KG anchor
  "https://en.wikipedia.org/wiki/Acme_Corp",        // REQUIRED: Tier-1 narrative anchor
  "https://www.crunchbase.com/organization/acme",   // Recommended: Tier-2 business registry
  "https://www.linkedin.com/company/acme-corp",     // Recommended: Tier-3 social proof
  "https://github.com/acme-corp"                    // Optional: Tier-3 dev community
]
```

---

## 4. Quotable Definition Sentence Standards

### 4.1 What Makes a Sentence AI-Quotable?

AI answer engines prefer sentences that are:
- **Self-contained**: Understandable without context from surrounding text.
- **Factual**: Contains at least one verifiable, specific claim.
- **Structured**: Follows a recognisable "X is a [type] that [does Y]" pattern.
- **Concise**: Ideally 20–50 words (fits in a featured snippet or AI answer card).

### 4.2 Quotability Scoring

| Trait               | Good Example                                       | Poor Example                            |
|:--------------------|:---------------------------------------------------|:----------------------------------------|
| **Entity anchor**   | "Acme is an enterprise..."                        | "We are passionate about..."            |
| **Type declaration** | "...automation platform..."                       | "...solutions provider..."             |
| **Audience**        | "...for Fortune 500 operations teams"             | "...for businesses of all sizes"       |
| **Outcome metric**  | "...reducing latency by 70%"                      | "...improving efficiency"              |
| **Avoids jargon**   | "automates order fulfilment workflows"            | "delivers innovative, cutting-edge synergies" |

### 4.3 Jargon Words That Reduce Quotability

The following words trigger `F-ENT-007` when ≥3 appear in a definition sentence:

```
innovative, innovation, cutting-edge, revolutionary, disruptive,
world-class, best-in-class, next-generation, next-gen, state-of-the-art,
transformative, game-changing, groundbreaking, paradigm, synergy,
holistic, seamless, frictionless, end-to-end, leverage, empower,
reimagine, thought-leadership, ecosystem, future-proof, enterprise-grade,
industry-leading, market-leading, best-of-breed, turnkey, value-added
```

### 4.4 Definition Placement Priority

| Location                     | AI Extraction Probability | Notes                                    |
|:-----------------------------|:--------------------------|:-----------------------------------------|
| `<meta name="description">`  | ⭐⭐⭐⭐⭐ Highest            | Directly indexed by all major crawlers   |
| First `<p>` in `<main>`      | ⭐⭐⭐⭐ High                | Above-the-fold body text                 |
| `<h1>` subheading (`<h2>`)   | ⭐⭐⭐ Medium               | Heading-level chunking in RAG systems    |
| Organization `description`   | ⭐⭐⭐⭐ High                | Schema.org structured field              |
| Buried in body paragraphs    | ⭐ Low                    | May be below RAG chunk boundary          |

---

## 5. hreflang & Locale Grounding Standards

### 5.1 hreflang Requirements

```html
<!-- Required pattern for multi-region / multi-language sites -->
<link rel="alternate" hreflang="en"    href="https://acme.com/en/"    />
<link rel="alternate" hreflang="en-GB" href="https://acme.com/en-gb/" />
<link rel="alternate" hreflang="de"    href="https://acme.com/de/"    />
<link rel="alternate" hreflang="fr"    href="https://acme.com/fr/"    />
<link rel="alternate" hreflang="x-default" href="https://acme.com/"  />
```

> **x-default is mandatory** — it defines the fallback page when no language
> match is found. Omitting it causes AI crawlers to arbitrarily select a language version.

### 5.2 geo-meta Tags (Local SEO & AI Regional Routing)

```html
<meta name="geo.region"    content="US-CA" />
<meta name="geo.placename" content="San Francisco, CA" />
<meta name="geo.position"  content="37.7749;-122.4194" />
<meta name="ICBM"          content="37.7749, -122.4194" />
```

### 5.3 Schema.org Locale Fields

```json
{
  "@type": "Organization",
  "areaServed": ["US", "GB", "CA", "AU", "DE"],
  "inLanguage": ["en", "de"],
  "audience": {
    "@type": "Audience",
    "audienceType": "Enterprise B2B",
    "geographicArea": {
      "@type": "AdministrativeArea",
      "name": "North America"
    }
  }
}
```
