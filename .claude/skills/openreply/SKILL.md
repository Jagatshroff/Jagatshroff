---
name: openreply
description: Set up OpenReply, a self-hosted open-source alternative to ManyChat for Instagram comment-to-DM automation. It watches comments on your Instagram posts via the official Meta API and, when a comment matches a keyword, sends that person a private DM (and optionally a public reply). Use when the user wants to automate Instagram comment-triggered DMs on their own infrastructure.
---

# OpenReply

Self-hosted Instagram comment→DM automation (`diwenne/openreply`, MIT). Someone comments
a keyword on your reel; OpenReply queues a DM with your link through the official Meta API.

## Where it lives
Cloned at `~/tools/openreply`. Self-hosted — you deploy your own copy; there is no hosted service.

## How to use
- Deploy your own instance (see the repo's deploy docs). Runs campaigns, queues, logs and
  inbox on your own infrastructure.
- Connect Instagram via your own Meta app, or the optional Zernio provider (see `docs/zernio.md`).

## Configuration (required)
- A **Meta/Instagram app** with the messaging permissions, or a Zernio connection.
- Hosting for the dashboard + worker.

## When to use
Automating keyword-triggered Instagram DMs/public replies, self-hosted. Not a hosted SaaS.
