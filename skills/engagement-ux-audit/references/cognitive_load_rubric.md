# Cognitive Load & Readability Rubric for AI-Referred Content

This document outlines the readability metrics and scannability benchmarks used to evaluate on-site comprehension and engagement for visitors landing from AI citations.

---

## 1. The Flesch Reading Ease Formula

The Flesch Reading Ease metric measures textual readability on a scale of 0 to 100:

$$\text{Flesch Reading Ease} = 206.835 - 1.015 \left(\frac{\text{Total Words}}{\text{Total Sentences}}\right) - 84.6 \left(\frac{\text{Total Syllables}}{\text{Total Words}}\right)$$

### Benchmark Scoring Table:

| Flesch Score | Reading Level | Typical Audience | AI Referral Suitability |
| :---: | :--- | :--- | :--- |
| **90 – 100** | Very Easy | 5th grade student | High (Instant comprehension) |
| **70 – 89** | Fairly Easy / Standard | 7th – 8th grade | **Optimal for B2B & B2C SaaS** |
| **60 – 69** | Standard | 8th – 9th grade | Good |
| **40 – 59** | Fairly Difficult | High school / College | Acceptable for deep technical specs |
| **0 – 39** | Very Confusing / Dense | Academic research / Legal | **Poor (High bounce risk: F-ENG-006)** |

---

## 2. Sentence Length & Structural Complexity

- **Optimal Average Sentence Length**: 14 to 20 words.
- **Danger Zone**: Average sentence length $> 25$ words indicates compound clauses and excessive passive voice that increase cognitive fatigue.

---

## 3. Scannability Formatting Benchmarks (F-ENG-007)

AI assistants present answers using bullet points, numbered lists, bold text, and concise paragraphs. When users land on a website, they scan rather than read linearly.

### Mandatory Scannability Features for Long-Form Content (> 500 words):
1. **Bulleted Lists (`<ul>`, `<ol>`)**: At least one list per 400 words to break down features or steps.
2. **Bold Highlights (`<strong>`, `<b>`)**: Bold lead-in keywords at the start of paragraphs or bullet points to guide visual skimming.
3. **Paragraph Brevity**: Paragraphs should not exceed 100 words or 5 sentences. Walls of text exceeding 150 words cause visual fatigue and immediate abandonment.
