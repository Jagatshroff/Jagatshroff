---
name: llm-council
description: Run karpathy's LLM Council — a local web app that sends one query to several LLMs via OpenRouter, has them anonymously review and rank each other's answers, then a Chairman model writes the final response. Use when the user wants multiple models' side-by-side opinions and cross-rankings on a question, or asks to start/configure the LLM Council app.
---

# LLM Council

Local web app by Andrej Karpathy (`karpathy/llm-council`). Instead of asking one
model, it queries a "council" of models through OpenRouter, has each anonymously
rank the others' answers, and a Chairman model compiles the final response.

## Where it lives
Cloned at `~/tools/llm-council`. Managed with `uv`.

## How it works
1. **First opinions** — the query goes to every configured model; answers collected.
2. **Review** — each model sees the others' answers (identities hidden) and ranks them.
3. **Final** — the Chairman model merges everything into one answer.

## Run it
```bash
cd ~/tools/llm-council
# Backend + frontend per README; uses uv for Python deps.
./start.sh            # starts the local web app
```

## Configuration (required before use)
- Needs an **OpenRouter API key** (`OPENROUTER_API_KEY`) — set it in the environment
  or the app's config before starting.
- Edit the council roster and the Chairman model in the project's config (see
  `main.py` / `pyproject.toml` and the README).

## When to use
The user wants several LLMs' answers to the same prompt compared side by side, with
the models critiquing each other — not a single-model answer.
