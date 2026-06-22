---
kind: readme
title: "<Client Name> — client"
---

# <Client Name>

Non-authoritative summary. The authoritative record is the `client` DB row.
Manage via `POST /clients` / `PUT /clients/<slug>`.

## Quick reference

| Field | Value |
|---|---|
| Slug | `<client-slug>` |
| Brand | `/brands/<client-slug>/brand.md` |
| Engagements | `/consulting/engagements/*-<client-slug>/` |

## Engagement context

_Paste key context here that should be injected into generator prompts for this client:
industry, ERP system, key stakeholders, terminology preferences, known constraints._
