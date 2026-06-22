---
name: anaplan-test-case-generator-prompt
kind: prompt
title: "Prompt: Anaplan test case generator (from FRD)"
status: draft
quality: 3
tags: [anaplan, testing, uat, generation, stub]
delivery_function: [testing]
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
  related: [anaplan-frd-template, anaplan-test-plan-template]
  supersedes: []
fingerprint: ""
created_at: 2026-06-22
updated_at: 2026-06-22
---

# Prompt: Anaplan test case generator

Takes a Functional Requirements Document as input and emits a structured test case workbook (one row per acceptance criterion).

## Inputs

- FRD markdown or DOCX content
- Optionally: persona list, module inventory (to enrich test data)

## Outputs

- Tabular test cases:
  - ID (auto-numbered)
  - Linked requirement ID
  - Test type (SIT / UAT / regression)
  - Pre-condition
  - Steps (numbered)
  - Expected result (data values, dashboard state)
  - Test data hint
  - Priority

## How we'd use it

- Run after the FRD is signed off
- Output feeds the Test Plan (see [anaplan-test-plan-template](anaplan-test-plan-template.md))
- Tester reviews and prunes — generator covers ~80% of cases; the last 20% needs human judgment

> **Status:** stub. Prompt text needs to be authored (likely as a Claude Code prompt in `/claude/prompts/`).
