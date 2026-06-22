---
name: anaplan-integration-spec-template
kind: template
title: "Template: Anaplan Integration Specification"
status: reviewed
quality: 3
tags: [anaplan, integration, cloudworks, etl, template, stub]
delivery_function: [integration]
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
  related: [anaplan-data-hub-spec-template]
  supersedes: []
fingerprint: ""
created_at: 2026-06-22
updated_at: 2026-06-22
---

# Integration Spec — Anaplan

Per-integration design: source, target, transport, schedule, error handling, contacts.

## Sections (one per integration)

- Integration name and direction (inbound / outbound / bi-directional)
- Source system and table/object reference
- Target model + import action chain
- Transport: CloudWorks / Informatica / Mulesoft / SFTP / custom API
- Field-level mapping with transformations
- Refresh schedule and dependencies
- Reconciliation method (control totals, row counts)
- Failure mode and on-call contacts
- Test data set and UAT sign-off

## How we use it

- One Integration Spec per inbound or outbound flow
- Owner: Integration Lead (often a non-Anaplan resource — ETL/middleware team)
- Becomes the contract between Anaplan team and integration team

> **Status:** stub. Replace with the firm's actual integration spec template.
