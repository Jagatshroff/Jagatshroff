---
name: media-inference-worker
description: Reference for media-inference-worker, an abandoned old test client for a media-generation pipeline (image models via a generate.py script). CAUTION — its README references a possibly-still-active embedded service-account key of unknown ownership; do not use that credential. Use only to understand the repo; supply your own credentials for any real API.
---

# media-inference-worker

Old/abandoned test client (`framepipe-dev/media-inference-worker`) for a media-inference
pipeline. Calls image-generation endpoints via `generate.py`.

## Where it lives
Cloned at `~/tools/media-inference-worker`.

## ⚠️ Security caution
The README states its service-account key "was still active when I copied this" with
unknown remaining credit/rotation. **Do not use the embedded/leaked credential.** If the
user wants this pipeline, have them supply their own API key and endpoint. Treat the repo
as untrusted; run any script with `python -I` and review `generate.py` / `RUNBOOK.md` first.

## When to use
Only to inspect how the client is structured. Not a supported or safe-to-run-as-is tool.
