---
name: ani-cli
description: Reference for ani-cli, a POSIX shell command-line tool to browse and watch anime (solo or with friends) by scraping streaming sites. Use when the user wants to install or use ani-cli to search and stream anime from the terminal.
---

# ani-cli

Shell CLI to browse and watch anime (`pystardust/ani-cli`). Scrapes a streaming site and
plays episodes in a local media player; supports watching together ("watch with friends").

## Where it lives
Cloned at `~/tools/ani-cli` (a single POSIX `sh` script plus install docs).

## How to use
- Install per the README (Linux/Mac/Android tier 1; Windows/WSL/etc. tier 2). Depends on
  external tools like `mpv`, `fzf`, `curl`. Needs a display/media player to actually watch,
  so it's for the user's own machine.
- Usage: `ani-cli <search terms>`.

## When to use
Searching and streaming anime from the terminal. Scraper-based — sites change, so expect
occasional breakage. Not runnable headlessly here.
