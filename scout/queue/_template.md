---
name: candidate-slug-best-guess          # Best-guess slug; finalised on promotion to /catalog/
kind: repo                                # Best-guess kind; can change on review
title: "Title from source"
status: draft

tags: []                                  # Optional; scout may pre-populate from source signals

source:
  type: github                            # Where the artifact lives
  url: https://github.com/...
  authors: []                             # Best-guess authors
  license: ""

discovered:
  via: hackernews                         # Slug of the discovery source
  on: 2026-06-14
  run_id: scout-2026-06-14-001

# Optional: scout-provided context
scout:
  raw_title: "Title as it appeared on the source"
  raw_url: "URL of the post/listing where we found it"
  score: 42                               # HN points, reddit upvotes, etc.
  excerpt: |
    First paragraph or first 500 chars of the source content, for at-a-glance review.

created_at: 2026-06-14
updated_at: 2026-06-14
---

# Reviewer notes

(Empty. The human reviewer fills this in as they decide what to do with the candidate.)
