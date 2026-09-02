# Information Density & AI Summarization Resilience Rubric (Appendix F)

This reference defines the information density scoring algorithm, buzzword taxonomy,
summarization resilience simulation, and thresholds used by the `freshness-corroboration`
skill (Subskill 4.3: `information_density_evaluator.py`).

---

## 1. The Information Density Problem

When AI email assistants, article summarizers (Claude, Gemini, ChatGPT), and Perplexity
digest web pages, they perform **extractive or abstractive compression** — typically
retaining 20%–40% of source tokens in the output summary.

Pages with **low information density** (high proportion of marketing filler, buzzwords,
and vague promotional language relative to substantive facts) suffer a critical failure:

> The genuine factual substance is diluted by noise. After AI compression, the retained
> 30% tokens are disproportionately noise, and the actual facts are dropped.

```
High-Density Page (60% substance):
  → AI compresses 30% → Retains ~18% of total → FACTS PRESERVED ✓

Low-Density Page (20% substance):
  → AI compresses 30% → Retains ~6% of total  → FACTS DROPPED ✗
```

---

## 2. Token Classification Framework

Visible body text tokens are classified into three mutually exclusive buckets:

### Bucket A — Substantive / Factual Tokens (Counted in density numerator)
- **Named entities**: Organization names, product names, people names, place names.
- **Technical terminology**: API endpoints, protocol names, algorithm names, acronyms.
- **Numerical data**: Specific numbers, percentages, currency values, measurements, dates.
- **Technical verbs**: "encrypts", "deploys", "monitors", "validates", "processes", "computes".
- **Specifications**: Version numbers, SLA percentages, throughput figures, latency targets.
- **Domain-specific nouns**: "Kubernetes cluster", "OAuth 2.0", "CI/CD pipeline", "LLM inference".

### Bucket B — Marketing Fluff / Buzzwords (NOT counted; actively dilute density)
High-risk marketing phrases that trigger density failure:

| Buzzword Pattern | Category |
| :--- | :--- |
| `"next-generation"`, `"next-gen"`, `"cutting-edge"` | Temporal hype |
| `"revolutionary"`, `"game-changing"`, `"groundbreaking"` | Superlative hype |
| `"paradigm shift"`, `"paradigm-shifting"` | Consulting jargon |
| `"seamless"`, `"frictionless"`, `"effortless"` | UX vagueness |
| `"best-in-class"`, `"best-of-breed"`, `"world-class"` | Comparative hype |
| `"synergy"`, `"synergize"`, `"leverage synergies"` | Business jargon |
| `"empower"`, `"empowering"`, `"unleash"`, `"unlock"` | Motivational vagueness |
| `"innovative"`, `"innovate"`, `"disruptive"`, `"disrupt"` | Startup clichés |
| `"holistic"`, `"end-to-end"` (without specifics), `"360-degree"` | Scope vagueness |
| `"transform"`, `"transformative"`, `"digital transformation"` | Consulting jargon |
| `"solutions"` (standalone, without specifying what), `"platform"` (vague) | Category vapour |
| `"thought leader"`, `"industry leader"`, `"market leader"` | Self-designation |
| `"bespoke"`, `"tailor-made"`, `"customized"` (without specifics) | Vague customization |

### Bucket C — Functional / Grammatical Tokens (Not counted toward substance or noise)
- Stopwords: `"the"`, `"a"`, `"and"`, `"or"`, `"in"`, `"of"`, `"for"`, `"to"`, `"is"`, `"are"`, etc.
- Prepositions, conjunctions, articles, auxiliary verbs.
- Punctuation marks.

---

## 3. Information Density Score Formula

$$\text{Information Density Score (\%)} = \frac{\text{|Bucket A Tokens|}}{\text{|Bucket A Tokens| + |Bucket B Tokens| + |Significant Content Tokens|}} \times 100$$

For practical implementation, the denominator uses all non-stopword content tokens
(Bucket A + Bucket B + domain neutral content words), providing a stable, comparable score.

---

## 4. Density Score Thresholds & Severity Mapping

| Density Score | Interpretation | Severity | Finding Triggered |
| :--- | :--- | :--- | :--- |
| **> 45%** | Optimal: High factual density; AI summaries reliably retain facts | Pass | None |
| **30% – 45%** | Warning: Medium density; some facts may be dropped in compression | `Medium` | F-FRSH-006 |
| **< 30%** | Critical: Low density; AI summaries predominantly retain noise over facts | `High` | F-FRSH-006 |

---

## 5. Appendix F Summarization Resilience Simulation

The evaluator simulates AI summarization compression to directly measure fact-retention:

### Simulation Algorithm:
1. Extract the top-N substantive sentences ranked by their Bucket A token concentration (ratio of factual tokens per sentence).
2. Simulate the "top 30% token retention" compression that AI extractive summarizers apply.
3. Check whether the core brand claims (name, product, primary value proposition) survive in the retained 30%.
4. If the simulated summary loses > 50% of identified factual claims, flag `F-FRSH-007`.

### Worked Example:

**Original page (200 words):**
> *"Acme Cloud is a revolutionary, next-generation platform that empowers modern enterprises to unlock synergistic value through our best-in-class holistic solution stack. Acme Cloud was founded in 2018 and processes 10 billion API calls per day across 40 data centers in 15 countries. Our innovative approach disrupts traditional paradigms with seamless frictionless excellence."*

**Token Analysis:**
- Bucket A (substantive): `Acme Cloud`, `2018`, `10 billion`, `API calls`, `40 data centers`, `15 countries` → 6 units
- Bucket B (fluff): `revolutionary`, `next-generation`, `empowers`, `unlock`, `synergistic`, `best-in-class`, `holistic`, `innovative`, `disrupts`, `paradigms`, `seamless`, `frictionless` → 12 units
- Density Score: `6 / (6 + 12 + ~20 neutral)` ≈ **16%** → `F-FRSH-006` (High)

**After 30% AI compression (60 words retained):**
> *"Acme Cloud is a revolutionary next-generation platform that empowers enterprises to unlock synergistic value through best-in-class solutions."*

Key facts **DROPPED**: founding year, 10 billion API calls, 40 data centers, 15 countries → `F-FRSH-007` triggered.

---

## 6. Minimum Viable Density Benchmark

For core product and landing pages, the following token ratios are benchmarks:

| Content Type | Minimum Density Target | Example of Good Density |
| :--- | :--- | :--- |
| SaaS product page | >= 35% | "Encrypts data using AES-256 at rest and TLS 1.3 in transit" |
| API documentation | >= 50% | "POST /v2/events returns 201 with event_id UUID within 200ms" |
| Pricing page | >= 40% | "Starter: 10,000 API calls/month — $29/mo; Pro: 500,000 calls — $199/mo" |
| Blog / thought leadership | >= 25% | Narrative content; lower threshold acceptable |
| About / team page | >= 20% | Lower density acceptable for storytelling pages |
