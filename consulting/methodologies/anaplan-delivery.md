---
name: anaplan-delivery
title: "Anaplan engagement delivery methodology"
applies_to:
  engagement_types: [anaplan-implementation, anaplan-optimization, anaplan-coe-setup, anaplan-rescue]
status: draft
version: 0.1
created_at: 2026-06-22
updated_at: 2026-06-22
---

# Anaplan engagement delivery methodology

The playbook for an end-to-end Anaplan engagement, organized by the `delivery_function` taxonomy (see [conventions/delivery-functions.md](../../conventions/delivery-functions.md)).

> **Status:** v0.1 draft. Refine from real engagement experience — this codifies the structure but the per-phase guidance needs sharpening with lessons-learned.

## How to use this document

- **For a new engagement:** walk top-to-bottom, lifting templates and skills from the catalog as you go.
- **For mid-engagement:** jump to the relevant phase, see what deliverables should be in flight, what tools to apply.
- **For estimating:** the durations below are rough Greenfield-implementation defaults — adjust for scope and team velocity.

Every template referenced here lives at `/catalog/templates/<slug>.md`; every skill at `/catalog/<slug>.md`. The static export ships them so client-side stakeholders can browse independently.

---

## Phase 1 — Discovery & Assessment

**Duration:** 2–4 weeks
**Goal:** Understand current state. Inventory data sources. Surface the planning processes that the Anaplan solution will replace or augment.

### Activities

- Stakeholder interviews (sponsor, planners, IT/data team, finance leadership)
- Process walk-throughs of the as-is planning cycle
- Data source inventory (which systems, what cadence, who owns each)
- Pain-point capture and outcome alignment
- "Day in the life" shadowing where possible

### Deliverables

- Current State Assessment (deck)
- Data source inventory (workbook)
- Stakeholder map and RACI

### Templates & skills

- [anaplan-frd-template](../../catalog/templates/anaplan-frd-template.md) — start sketching the FRD outline; finalize in Phase 2

### Common pitfalls

- **Talking only to IT.** The planners are the users; their workflow is the source of truth.
- **Skipping data quality assessment.** A clean data hub depends on understanding source-system mess *before* design starts.

---

## Phase 2 — Requirements

**Duration:** 3–6 weeks
**Goal:** Lock what the solution must do, in language that's specific enough to build against and clear enough for business to sign off.

### Activities

- Requirements workshops (one per process area, typically 4–6 sessions)
- Use case authoring with acceptance criteria
- Data and reporting requirements specification
- Out-of-scope explicit list
- Sign-off workshop with sponsor + business lead

### Deliverables

- **Functional Requirements Document (FRD)** — [anaplan-frd-template](../../catalog/templates/anaplan-frd-template.md)
- Use case inventory with priorities (must / should / could)
- Data requirements matrix (what data, from where, refresh cadence)

### Templates & skills

- [anaplan-frd-template](../../catalog/templates/anaplan-frd-template.md)
- [anaplan-module-spec-generator-prompt](../../catalog/anaplan-module-spec-generator-prompt.md) — first-pass module proposals from requirements

### Common pitfalls

- **Starting architecture before requirements are locked.** The #1 cause of rebuild work. If a stakeholder hasn't signed off, the requirement isn't done.
- **Vague acceptance criteria.** "The system should be fast" is not testable. Tie every requirement to a measurable outcome.

---

## Phase 3 — Architecture & Design

**Duration:** 2–4 weeks
**Goal:** Lock the model topology before any builder writes a formula.

### Activities

- Hub/spoke decision and workspace sizing
- List and hierarchy design (the structural backbone)
- Module inventory with purpose and dimensionality
- Data hub design (separate from spokes)
- Dashboard/UX design (low-fi sketches; high-fi in Build)
- Architecture review against Anaplan Model Building Standards ([anapedia](../../catalog/anapedia.md))

### Deliverables

- **Model Design Spec (MDS)** — [anaplan-model-design-spec-template](../../catalog/templates/anaplan-model-design-spec-template.md)
- **Hierarchy & Lists Design** — [anaplan-hierarchy-design-template](../../catalog/templates/anaplan-hierarchy-design-template.md)
- **Data Hub Spec** — [anaplan-data-hub-spec-template](../../catalog/templates/anaplan-data-hub-spec-template.md)

### Templates & skills

- The three templates above
- [anaplan-hierarchy-auditor-skill](../../catalog/anaplan-hierarchy-auditor-skill.md) — validate the proposed hierarchy before it locks

### Common pitfalls

- **Over-stuffed lists.** A list with >5 subsets degrades performance. Split early.
- **No data hub.** Loading source data directly into spoke models couples everything to source schema. Always design a hub first.
- **List restructures mid-build.** Cost compounds with every module that depends on the list. Lock the hierarchy in Phase 3, not Phase 4.

---

## Phase 4 — Build

**Duration:** 6–12 weeks (scope-dependent)
**Goal:** Build the model per spec, in iterative sprints with regular show-and-tell.

### Activities

- Module-by-module construction following the MDS
- Pair-building for complex formulas
- Sprint demos every 2 weeks (stakeholders see real model, not slides)
- Internal QA at sprint boundaries
- Documentation as you go (don't defer to "after build")

### Deliverables

- Working Anaplan model in DEV environment
- Module Detail Specs (one per module, written *during* build, not before)
- Demo recordings (for stakeholders who miss sessions)

### Templates & skills

- [anaplan-formula-reviewer-skill](../../catalog/anaplan-formula-reviewer-skill.md) — catch formula anti-patterns before they accumulate
- [supabase-skill](../../catalog/supabase-skill.md) + [supabase-postgres-best-practices-skill](../../catalog/supabase-postgres-best-practices-skill.md) — when a data hub is implemented on Postgres / Supabase between source systems and Anaplan

### Common pitfalls

- **Big-bang demos.** Demoing at end of build is too late to course-correct. Demo every 2 weeks against signed-off use cases.
- **Skipping standards review.** A model that ignores Anaplan Model Building Standards costs 2–3x more to maintain.

---

## Phase 5 — Integration

**Duration:** Concurrent with Phase 4 (3–8 weeks)
**Goal:** Wire the model into the surrounding system landscape.

### Activities

- Connector setup (CloudWorks, Informatica, Mulesoft, custom API)
- Source system field-mapping and transformation logic
- Test data load with reconciliation
- Refresh schedule design (avoid overlap with batch close)
- Error-handling and alerting design

### Deliverables

- **Integration Specs** — [anaplan-integration-spec-template](../../catalog/templates/anaplan-integration-spec-template.md), one per flow
- Reconciliation procedure (per integration)
- Connector configuration (typically owned by client IT)

### Common pitfalls

- **Treating integration as Phase 6.** Integration belongs alongside Build, not after. Late integration discovers source-system surprises that force model rework.
- **No reconciliation logic.** Without a control-total check, you'll catch data quality issues weeks late.

---

## Phase 6 — Testing & Validation

**Duration:** 3–6 weeks (overlapping Build tail)
**Goal:** Prove the system works against signed-off requirements, with business users in the driver's seat.

### Activities

- SIT (system integration testing) — end-to-end with real integrations
- UAT (user acceptance testing) — business users execute test cases
- Performance testing (workspace size, calc time, dashboard load)
- Defect lifecycle: log → triage → fix → retest → close
- UAT sign-off (gate to Phase 7)

### Deliverables

- **Test Plan** — [anaplan-test-plan-template](../../catalog/templates/anaplan-test-plan-template.md)
- Test case workbook (one row per acceptance criterion)
- UAT defect log with closure status
- Signed UAT acceptance memo

### Templates & skills

- [anaplan-test-plan-template](../../catalog/templates/anaplan-test-plan-template.md)
- [anaplan-test-case-generator-prompt](../../catalog/anaplan-test-case-generator-prompt.md) — first-draft test cases from the FRD; tester reviews and prunes

### Common pitfalls

- **UAT with consultants, not business users.** Defeats the purpose. If the planners aren't testing, you haven't done UAT.
- **No regression pack.** Without one, you can't safely do hypercare fixes.

---

## Phase 7 — Deployment

**Duration:** 1–2 weeks (planning) + cutover window + 2–4 weeks hypercare
**Goal:** Move from DEV/TEST to production with a rollback path and active support.

### Activities

- Pre-cutover readiness review (UAT sign-off, sign-off log, rollback plan)
- Cutover rehearsal (tabletop)
- Production cutover (typically a weekend)
- Hypercare with enhanced staffing
- Transition to BAU support

### Deliverables

- **Cutover Plan** — [anaplan-cutover-plan-template](../../catalog/templates/anaplan-cutover-plan-template.md)
- Production environment with users provisioned
- Hypercare log
- Handover memo to BAU support

### Templates & skills

- [anaplan-cutover-plan-template](../../catalog/templates/anaplan-cutover-plan-template.md)

### Common pitfalls

- **No rehearsal.** Cutovers go wrong in subtle ways. A tabletop catches 80% of issues before they're real.
- **Hypercare with skeleton crew.** First two weeks post-go-live are when 70% of post-cutover issues surface. Plan accordingly.

---

## Phase 8 — Training & Enablement

**Duration:** 2–3 weeks (concurrent with Phase 6–7)
**Goal:** Ensure end users can actually use the system on day one of go-live.

### Activities

- Persona-shaped training material authoring
- Live training sessions (virtual + recorded)
- Job aids and quick-reference cards
- Champion network identification (power users who help peers)
- Admin training for Anaplan model owners (separate track)

### Deliverables

- **End-User Training Deck** — [anaplan-training-deck-template](../../catalog/templates/anaplan-training-deck-template.md)
- Job aids (one per persona)
- Admin runbook (operational ownership doc)
- Training session recordings

### Templates & skills

- [anaplan-training-deck-template](../../catalog/templates/anaplan-training-deck-template.md)

### Common pitfalls

- **Generic training.** A planner uses the model differently than an approver. Persona-shape the materials.
- **No champions.** Power users who help peers are 10x more effective than escalations to consultants.

---

## Phase 9 — Change Management *(cross-cutting)*

**Duration:** Concurrent with Phases 1–8
**Goal:** Manage the human side of the transformation so adoption sticks.

### Activities

- Change impact assessment (who's affected, how)
- Stakeholder communication plan
- Adoption tracking (login frequency, dashboard usage, plan submission rates)
- Resistance management (early-warning system for problem stakeholders)

### Deliverables

- Change impact assessment
- Communication plan with cadence
- Adoption dashboard (often built in Anaplan itself)

### Common pitfalls

- **Change-mgmt as an afterthought.** Decide on a CM lead in Week 1. The cost of late attention compounds.

---

## Phase 10 — Reporting & PMO *(cross-cutting)*

**Duration:** Continuous
**Goal:** Keep leadership informed; surface risks before they become issues.

### Activities

- Weekly status reports (end-of-week)
- Steering committee meetings (typically bi-weekly)
- RAID log maintenance
- Decision log (every meaningful decision recorded)
- Budget/burn tracking

### Deliverables

- **Status Report** — [anaplan-status-report-template](../../catalog/templates/anaplan-status-report-template.md), weekly
- RAID log (live document)
- Steering committee decks (bi-weekly)

### Templates & skills

- [anaplan-status-report-template](../../catalog/templates/anaplan-status-report-template.md)

### Common pitfalls

- **Output-focused status reports.** "We built 7 modules" isn't a status — it's a log. Lead with outcomes (use cases met, milestones hit) and risks.
- **Decisions made in hallways.** If it's not in the decision log, it didn't happen. Future-you (and your successor consultant) will thank you.

---

## What separates this methodology

- **Agentic toolkit is assumed.** Skills like the formula reviewer and test-case generator are part of the team. Capacity assumptions reflect this leverage.
- **Catalog-driven learning.** Patterns from each engagement contribute back to `/catalog/` and `/claude/`. The toolkit gets better per engagement.
- **Templates ship.** Stakeholders can browse the deliverable shape via the static catalog export *before* committing to the engagement. Reduces sales-cycle ambiguity.

## Estimating shorthand

A typical Greenfield Anaplan implementation (one process area, e.g., workforce planning):
- **Discovery + Requirements:** 6–10 weeks
- **Architecture:** 3 weeks
- **Build + Integration + Testing:** 12–16 weeks (overlapping)
- **Training + Deployment:** 3–4 weeks
- **Hypercare:** 2–4 weeks
- **Total elapsed:** 4–6 months
- **Team:** Sol Arch (1, 50%), Lead Builder (1, 100%), Builder (1–2, 100%), Integration Lead (1, 50%), Test Lead (1, 50% peak), CM Lead (1, 25%), PM (1, 50%)

Multi-process or multi-region engagements scale roughly linearly on Build/Test, more steeply on Discovery/Requirements.
