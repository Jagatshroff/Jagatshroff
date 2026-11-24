---
name: oatmeal
description: Reference for Oatmeal, a Mac app for meeting notes and dictation. It records your mic and the other side of a call (Zoom/Meet/Teams/FaceTime) with no bot joining, transcribes locally, and has Claude Code, Codex, or Gemini CLI write Granola-style notes on your own plan; Oatmeal Capture also records the screen with zooms and camera. Use when the user wants local meeting transcription/notes or polished screen captures on a Mac.
---

# Oatmeal

Mac meeting-notes and dictation app (`bchong12/oatmeal`). Transcribes on-device; notes are
written by the AI CLI you already pay for (Claude Code, Codex, or Gemini CLI).

## Where it lives
Cloned at `~/tools/oatmeal`.

## What it does
- **Oatmeal Notes**: records mic + other side of a call (no bot joins), then an agent CLI
  writes Granola-style notes from the transcript.
- **Oatmeal Capture**: screen recording with camera/voice, click/typing zooms, screenshots;
  outputs raw + polished video and a transcript.

## How to use
- Native macOS app — install/build per the repo on the user's own Mac. It records audio/screen,
  so it cannot run in this headless container. Needs one of the supported agent CLIs for notes.

## When to use
Local, private meeting transcription + AI notes, or polished screen captures, on a Mac.
