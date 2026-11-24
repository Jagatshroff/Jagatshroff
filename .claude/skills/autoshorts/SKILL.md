---
name: autoshorts
description: Run AutoShorts, a local-first desktop app (Tauri 2 + React + Rust + SQLite) that turns long-form video or audio into ranked 9:16 short-form clip candidates with AI-powered viral-moment detection and hooks. Use when the user wants to import a recording, transcribe it, and get ranked vertical clip candidates locally.
---

# AutoShorts

Local-first desktop app (`JayWebtech/autoshorts`) that imports long video/audio,
extracts and transcribes audio, then analyzes and ranks viral moments into 9:16
clip candidates. Stores transcripts, candidates, and projects in local SQLite.

## Where it lives
Cloned at `~/tools/autoshorts` (Tauri 2 + React/TSX + Rust; `package.json`).

## Run it
```bash
cd ~/tools/autoshorts
npm install
npm run tauri dev        # desktop app in dev (needs the Rust/Tauri toolchain)
```
See the README for building a packaged desktop binary.

## Configuration
- Multi-LLM: **DeepSeek** (default) or **Claude** (Anthropic) for moment detection — set the provider key.
- Transcription uses **Deepgram** — needs a Deepgram API key.

## When to use
Turning a long recording into ranked vertical short-form clip candidates on the
desktop. (Desktop/GUI app — needs the user's own machine to actually display; here it
builds and runs headless-only.)
