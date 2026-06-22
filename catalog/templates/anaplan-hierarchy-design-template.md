---
name: anaplan-hierarchy-design-template
kind: template
title: "Template: Anaplan Hierarchy & Lists Design"
status: reviewed
quality: 3
tags: [anaplan, hierarchy, lists, template, stub]
delivery_function: [architecture]
source:
  type: manual
  url: ""
  authors: [forge]
  license: ""
discovered:
  via: manual
  on: 2026-06-22
relations:
  parent:
  related: [anaplan-model-design-spec-template]
  supersedes: []
fingerprint: ""
created_at: 2026-06-22
updated_at: 2026-06-22
---

# Hierarchy & Lists Design — Anaplan

Documents the structural backbone of the model: every list, hierarchy level, subset, line item subset, and the rationale for each.

## Sections

- Top-down list inventory with parent/child relationships
- Time settings (calendar, periods, fiscal year offset)
- List property usage (don't overload — split into modules where appropriate)
- Subset strategy (avoid >5 subsets per list — degrades performance)
- Line item subsets (LISS) for reporting flexibility
- Master data ownership: which list comes from which source system
- Versioning and reload policy

## How we use it

- Authored after the FRD but before any module build
- Reviewed by data-side counterparts (who owns the customer list? the product list?)
- Locked early — list restructures mid-build are expensive

> **Status:** stub. Replace with the firm's actual hierarchy design template.
