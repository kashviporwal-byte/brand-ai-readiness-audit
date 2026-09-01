# Non-Text Media & Machine Accessibility Standards

Guidelines for auditing non-text elements to ensure complete machine extractability and zero false positives.

---

## 1. Image Classification Heuristics

### Decorative Images (Ignore / Expected Empty Alt)
- Images marked with `role="presentation"` or `role="none"`.
- Images marked with `aria-hidden="true"`.
- Small UI icons, spacers, divider lines, and background ornaments (dimensions <= 16x16px).
- Images with explicit empty alt text (`alt=""`) that sit alongside descriptive adjacent text (e.g. icon next to a text label).

### Informational Images (Require High-Quality Alt)
- Architecture diagrams, workflow charts, data graphs.
- Product screenshots demonstrating UI features.
- Team photos or leadership headshots where the name/role is conveyed.
- Infographics containing statistics, percentages, or milestones.
- Company logos and partner trust badges.

---

## 2. Alt Text Quality Criteria

| Flag | Pattern | Example | Problem |
| :--- | :--- | :--- | :--- |
| **Missing Alt** | Attribute absent | `<img src="a.png">` | Screen readers and AI scrapers read URL or ignore |
| **Filename Alt** | Matches file pattern | `alt="diagram_v2_final.png"` | Technical clutter, zero semantic value |
| **Generic Placeholder** | Generic words | `alt="image"`, `alt="graphic"` | Low effort, provides no factual knowledge |
| **Low-Density Single Word** | 1 word for complex chart | `alt="chart"` on a complex plot | Insufficient detail for AI answer generation |
| **Descriptive (Pass)** | Factual & concise | `alt="Architecture diagram showing Redis cache between FastAPI server and PostgreSQL database"` | High informational density, readily quotable |

---

## 3. Media & Interactive Fallbacks

### Canvas Elements
- **Requirement**: Must have `aria-label`, `aria-describedby` pointing to a text summary, or fallback DOM text inside the `<canvas>` tags.

### Video / Audio
- **Requirement**: Must have at least one `<track kind="captions">` or `<track kind="subtitles">` with a valid `.vtt` file, OR an adjacent transcript block with class/id containing `transcript`.
