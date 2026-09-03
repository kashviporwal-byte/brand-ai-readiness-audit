# AI Crawler Signatures, Robots Directives, and llms.txt Standards

This reference documents the canonical user-agents, HTTP header controls, and modern AI manifest standards evaluated by `crawl-bot-access`.

## 1. AI Search Crawler User-Agents

AI assistants rely on specialized automated crawlers distinct from traditional Googlebot/Bingbot:

| Crawler User-Agent | Organization | Purpose | Priority Tier |
| :--- | :--- | :--- | :---: |
| `GPTBot` | OpenAI | ChatGPT search, grounding, and training retrieval | Tier 1 |
| `ClaudeBot` | Anthropic | Claude web search, real-time citation retrieval | Tier 1 |
| `PerplexityBot` | Perplexity AI | Real-time citation search indexing | Tier 1 |
| `Google-Extended` | Google | Controls Gemini training and retrieval grounding | Tier 2 |
| `Applebot-Extended`| Apple | Apple Intelligence search and Siri grounding | Tier 2 |
| `Amazonbot` | Amazon | Alexa & Rufus AI shopping/search discovery | Tier 2 |
| `Bytespider` | ByteDance | TikTok / AI search retrieval | Tier 2 |
| `CCBot` | Common Crawl | Training corpus indexing used by multiple models | Tier 2 |
| `cohere-ai` | Cohere | Enterprise RAG search and model grounding | Tier 2 |

## 2. HTTP X-Robots-Tag Directives

The `X-Robots-Tag` HTTP response header controls crawler indexing before the HTML payload is parsed:

* `noai` / `noimageai`: Explicitly forbids AI model ingestion and training.
* `noindex`: Disallows the page from entering the search index completely.
* `nosnippet`: Prevents search and AI engines from displaying text summaries or quoting answers.
* `unavailable_after`: Invalidates content after a specific timestamp.

## 3. The /llms.txt Standard

The `/llms.txt` standard (developed by Jeremy Howard and adopted across the AI community) provides a concise, structured markdown map specifically tailored for LLM context windows:

* **Location:** `https://example.com/llms.txt` and `https://example.com/llms-full.txt`
* **Format:** Clean Markdown beginning with `# Brand / Project Name`
* **Structure:**
  * Concise 2-sentence summary of the brand / service.
  * Bulleted markdown links to key documentation, API references, and product specifications.
  * Omission of HTML chrome, navigation menus, and client scripts.
