---
name: dead-link-asset
kind: article
title: Dead-link asset
status: reviewed
tags: []
source:
  type: article
  url: https://example.com/dead-link
  authors:
  - alice
  license: ''
discovered:
  via: manual
  'on': '2026-03-15'
created_at: '2026-03-15'
updated_at: '2026-03-15'
---

# Notes

The upstream URL has been 404 for weeks. Pass 4 should archive this once
the liveness checker records ≥3 consecutive 404s with `first_404` older
than 30 days.
