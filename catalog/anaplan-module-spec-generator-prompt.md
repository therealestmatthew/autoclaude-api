---
name: anaplan-module-spec-generator-prompt
kind: prompt
title: "Prompt: Anaplan module spec generator (from requirements)"
status: draft
quality: 3
tags: [anaplan, modules, requirements, generation, stub]
delivery_function: [requirements, architecture]
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
  related: [anaplan-frd-template, anaplan-model-design-spec-template]
  supersedes: []
fingerprint: ""
created_at: 2026-06-22
updated_at: 2026-06-22
---

# Prompt: Anaplan module spec generator

Takes a functional requirement (or cluster of requirements) and proposes a module-level spec — name, dimensions, line items, key formulas.

## Inputs

- Requirement statement(s) from the FRD
- Hierarchy Design Doc (so dimensions are pre-known)
- Optional: existing module inventory (to suggest reuse vs. create new)

## Outputs

- Proposed module name and purpose
- Dimensionality: which lists × time
- Line items with:
  - Format (NUMBER, BOOLEAN, list-formatted, …)
  - Aggregation method
  - Formula sketch (with TODO markers where business rules are unclear)
- Inputs from / outputs to (which modules this connects)
- Open questions for the business analyst

## How we'd use it

- First-draft tool used during requirements → architecture handoff
- Output is reviewed and refined by the Solution Architect
- Saves ~50% of the initial spec-authoring time on greenfield builds

> **Status:** stub. Prompt body needs authoring.
