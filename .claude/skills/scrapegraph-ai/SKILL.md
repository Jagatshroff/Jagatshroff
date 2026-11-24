---
name: scrapegraph-ai
description: Scrape and extract structured data from websites and local HTML/XML/JSON/Markdown using ScrapeGraphAI, a Python library that builds LLM-driven scraping pipelines (SmartScraperGraph, SearchGraph, etc.). Use when the user wants to pull structured data from a page or site by describing what they want in natural language rather than writing CSS/XPath selectors.
---

# ScrapeGraphAI

Python library (`scrapegraphai`) for LLM-powered web scraping: you give a prompt and
a source (URL or local file) and it returns structured data.

## Install / where it lives
- Installed via `pip install scrapegraphai` (already installed in this environment).
- Source clone for reference: `~/tools/Scrapegraph-ai`.
- Browser steps need Playwright; this environment ships a pre-installed Chromium.

## Minimal usage
```python
from scrapegraphai.graphs import SmartScraperGraph

graph = SmartScraperGraph(
    prompt="Extract the title, author and price of every book",
    source="https://example.com/books",      # URL or local file path/text
    config={
        "llm": {"model": "openai/gpt-4o-mini", "api_key": "..."},  # or anthropic/claude-*
    },
)
print(graph.run())
```

## Configuration (required before use)
- An **LLM provider key** (OpenAI, Anthropic, Gemini, or a local Ollama model) in `config["llm"]`.
- Run any script that reads downloaded/untrusted HTML with `python -I`.

## When to use
Structured extraction from web pages or documents described in plain language;
multi-page `SearchGraph`/`SmartScraperMultiGraph` jobs.
