---
name: delivery-functions
kind: convention
title: "Delivery functions — taxonomy for skills & tools"
status: active
version: "1.0"
created_at: 2026-06-22
updated_at: 2026-06-22
---

# Delivery Functions

The `delivery_function` frontmatter field on catalog assets (`kind: agent`, `skill`, `plugin`, `mcp`, `prompt`, `template`) maps tools to the phases of consulting delivery where they are useful.

A single asset can span multiple functions — list them all. Assets without `delivery_function` are treated as general-purpose utilities and appear in an "Ungrouped" section in the Skills & Tools UI.

## Usage in frontmatter

```yaml
# Single function
delivery_function: requirements

# Multiple functions (list)
delivery_function:
  - discovery
  - requirements
```

## Vocabulary

Defined Anaplan-first; the slugs are designed to extend cleanly to broader Finance Transformation delivery as the practice grows.

| slug | label | What tools/skills go here |
|------|-------|--------------------------|
| `discovery` | Discovery & Assessment | Current-state mapping, stakeholder interview guides, process documentation helpers, AS-IS analysis, data source inventory |
| `requirements` | Requirements | FRD/BRD generators, user story writers, acceptance criteria, data requirements docs, model design spec templates |
| `architecture` | Architecture & Design | Anaplan model structure decisions, hub/spoke design helpers, hierarchy planning, module/action mapping aids |
| `build` | Build | Model development aids, formula authoring, module wiring helpers, dashboard/UX creation, data transformation |
| `integration` | Integration | Data connector setup, CloudWorks flow authoring, API spec generation, ETL pipeline design and validation |
| `testing` | Testing & Validation | SIT/UAT script generators, test case templates, data reconciliation helpers, scenario validation |
| `deployment` | Deployment | Production migration checklists, data migration scripts, cutover planning, hypercare playbooks |
| `training` | Training & Enablement | End-user training decks, admin SOPs, job aids, knowledge-transfer templates, quick-reference guides |
| `change-mgmt` | Change Management | Change impact assessments, comms plan templates, stakeholder mapping, adoption trackers |
| `reporting` | Reporting & PMO | Status report generators, steering committee deck templates, RAID logs, decision logs, project trackers |

## Extension rules

- New slugs require a PR that updates this file and re-tags any affected assets.
- Slugs are kebab-case, kept short (one or two words). Labels are title-case for UI display.
- When a future practice area is added (e.g., SAP, Oracle EPM), add new slugs rather than reusing Anaplan-centric ones if the meaning would be ambiguous.
- Do not create one-off slugs for a single asset — if a tool doesn't fit existing functions, propose a new function slug here first.
