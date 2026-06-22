---
kind: convention
title: "Forge — Supported Deliverable Types"
status: active
updated_at: 2026-06-19
---

# Supported Deliverable Types

This is the running registry of document types that Forge can generate, composed, or templatize. Each entry maps to one or more `kind: template` assets in `/catalog/templates/` (when the template exists) and declares the canonical output format(s) and the business processes it serves.

Add a new row when: a template is built, a bundle references a new document type, or a consultant confirms a recurring deliverable pattern that should be standardized.

---

## Strategy & Assessment

| Deliverable | Abbrev | Formats | Business Processes | Template Status |
|---|---|---|---|---|
| Current State Assessment | CSA | pptx, pdf | R2R, O2C, P2P, FP&A | planned |
| Future State Vision | FSV | pptx, pdf | all | planned |
| Gap Analysis | — | pptx, pdf | all | planned |
| Executive Summary | ExecSum | pptx, docx, pdf | all | planned |
| Process Flow / Swim-lane Diagram | PFD | pptx, pdf | all | planned |

## Requirements

| Deliverable | Abbrev | Formats | Business Processes | Template Status |
|---|---|---|---|---|
| Functional Requirements Document | FRD | docx, pdf | all | planned |
| Business Requirements Document | BRD | docx, pdf | all | planned |
| Technical Design Document | TDD | docx, pdf | all | planned |
| Epics & User Stories | — | docx, xlsx, pdf | all | planned |
| Acceptance Criteria | AC | docx, pdf | all | planned |

## Technical

| Deliverable | Abbrev | Formats | Business Processes | Template Status |
|---|---|---|---|---|
| Integration Specification | IntSpec | docx, pdf | all | planned |
| Data Spec Sheet / Data Dictionary | DataSpec | xlsx, pdf | all | planned |
| API Specification | APISpec | docx, pdf | all | planned |
| System Architecture Document | SAD | docx, pdf | all | planned |
| Data Migration Plan | DMP | docx, pdf | R2R, O2C | planned |

## Project Management

| Deliverable | Abbrev | Formats | Business Processes | Template Status |
|---|---|---|---|---|
| Project Timeline / Gantt | Timeline | xlsx, pdf | all | planned |
| Status Report | StatusRpt | pptx, pdf | all | planned |
| Project Charter | Charter | docx, pdf | all | planned |
| RAID Log (Risk/Assumption/Issue/Dependency) | RAID | xlsx, pdf | all | planned |
| Decision Log | DecLog | xlsx, pdf | all | planned |
| Steering Committee Deck | SteerCo | pptx, pdf | all | planned |

## Proposals & Commercial

| Deliverable | Abbrev | Formats | Business Processes | Template Status |
|---|---|---|---|---|
| Proposal / Statement of Work | SOW | docx, pdf | all | planned |
| Pricing Sheet | — | xlsx, pdf | all | planned |
| Engagement Kickoff Deck | Kickoff | pptx, pdf | all | planned |

## Training & Adoption

| Deliverable | Abbrev | Formats | Business Processes | Template Status |
|---|---|---|---|---|
| Training Deck | TrainDeck | pptx, pdf | all | planned |
| Job Aid / Quick Reference Guide | QRG | docx, pdf | all | planned |
| Process Guide / SOP | SOP | docx, pdf | all | planned |
| Change Impact Assessment | CIA | docx, xlsx, pdf | all | planned |

---

## Template status values

- `active` — template exists in `/catalog/templates/`, generator wired, available in Forge UI
- `planned` — identified deliverable type; template not yet built
- `spike-needed` — type identified but format/generation approach needs investigation before building

## How to add a new deliverable type

1. Add a row to the table above with status `planned`.
2. Create the template asset at `/catalog/templates/<slug>.md` with `kind: template`.
3. Place the source file (`.pptx`, `.docx`, `.xlsx`) at `/catalog/templates/files/<slug>.<ext>`.
4. Wire a generator (`generator_kind`, `generator_slug`) in the template frontmatter.
5. Update template status to `active`.
6. Optionally compose into a bundle at `/catalog/bundles/<slug>.md`.
