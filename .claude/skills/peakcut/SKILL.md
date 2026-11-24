---
name: peakcut
description: Run PeakCut, an open-source tool that turns long videos and live streams (YouTube/Twitch/Kick links or uploads) into captioned 9:16 vertical clips, picking the moments worth clipping with your own AI key and optionally auto-posting to YouTube/Instagram/TikTok. Use when the user wants to clip long-form video into shorts, add word-by-word captions, or set up live-stream clipping.
---

# PeakCut

Open-source long-video-to-shorts tool (`haziqahmedqasmi/PeakCut`). Transcribes audio,
asks an AI which moments hold attention, cuts them to 9:16 with captions and a hook,
and can auto-post. Also records a live stream and clips highlights in real time.

## Where it lives
Cloned at `~/tools/PeakCut` (Python; `requirements.txt`, `docker-compose.yml`, `studio.server`).

## Run it
```bash
cd ~/tools/PeakCut
pip install -r requirements.txt        # first time
python -m studio.server                # opens the dashboard (long-running; ask before starting)
```
Docker mode is in `docker-compose.yml` / `DEPLOY.md`.

## Configuration
- Bring your own AI key: Gemini, OpenAI, Grok, Groq, OpenRouter, Claude, or local Ollama.
  With no key, clips are chosen by loudness only.
- Posting to YouTube/Instagram/TikTok needs the one-time OAuth setup in `DEPLOY.md`.
- On your own machine it opens straight to the dashboard; on a shared server set
  `PEAKCUT_ACCOUNTS=1` for sign-in.

## When to use
Clipping long videos/streams into captioned vertical shorts, or live highlight clipping.
