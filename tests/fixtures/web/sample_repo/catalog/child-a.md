---
name: child-a
kind: agent
title: "Child A"
status: reviewed
tags: [fixture]
source:
  type: github
  url: https://github.com/example/child-a
discovered:
  via: manual
  on: 2026-06-18
relations:
  parent: old-parent
  related: []
created_at: 2026-06-18
updated_at: 2026-06-18
---

Child A — points at old-parent. Used for cascade rename test.
