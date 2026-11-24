---
name: invoice-builder
description: Run Invoice Builder, an offline-first open-source invoicing and quoting app for freelancers and small businesses (Electron desktop, or self-hosted web/Docker). Use when the user wants to create or manage invoices and quotes locally, or asks to launch/self-host the Invoice Builder app.
---

# Invoice Builder

Offline-first invoicing and quoting app (`piratuks/invoice-builder`). No accounts, no
cloud — data lives in a local database file. Runs as an Electron desktop app or a
self-hosted web/Docker service.

## Where it lives
Cloned at `~/tools/invoice-builder` (TypeScript monorepo; `apps/`, `docker-compose.yml`).

## Run it
Self-hosted web mode via Docker (leaves a server running — ask before starting in a
shared session):
```bash
cd ~/tools/invoice-builder
docker compose up -d        # serves the web UI; see README for the port
```
Desktop/manual modes are in the README and https://piratuks.github.io/invoice-builder/.

## Configuration / cautions
- Data is stored in a local DB file you own; back it up before upgrades.
- v3.0.2 changed the migration path — back up and complete migrations through 2.10.0
  before upgrading an existing database.

## When to use
Creating, editing, or exporting invoices and quotes locally; standing up a private
invoicing instance. Not a hosted/SaaS billing integration.
