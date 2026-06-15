---
name: consulting-templates-readme
title: "/consulting/templates/ — engagement template catalog"
kind: readme
status: active
updated_at: 2026-06-15
---

# /consulting/templates/

Fill-in-the-blank documents reused across engagements. Each template is a single `.md` file with frontmatter and `{{placeholder}}` markers.

This README is the **template catalog**: every template the practice expects to need, with status. We don't build them up front — we build a template the first time we need it for a real engagement and freeze it once the second engagement reuses it. The catalog is here so the *shape* of what's missing is visible.

## How to read this catalog

| Column      | Meaning                                                                                       |
| ----------- | --------------------------------------------------------------------------------------------- |
| **Status**  | `built` (file exists) · `next` (build on first need) · `planned` (likely needed) · `deferred` (only if signal appears) |
| **Type**    | `project` (fixed-scope delivery) · `workshop` (enablement) · `both` · `cross` (business ops)  |
| **Publish** | `public-safe` (the *template* is publishable; filled instances may still be private) · `private` (template structure reveals pricing/legal posture; keep internal) |

The practice today serves two engagement archetypes: **fixed-scope project delivery** and **workshop / enablement**. Audit and retainer offerings are out of scope until demand signals otherwise.

## Pre-engagement (sales, qualification, contracting)

| Template                       | Type     | Status   | Publish     | Purpose                                                          |
| ------------------------------ | -------- | -------- | ----------- | ---------------------------------------------------------------- |
| `discovery-call-questions.md`  | both     | planned  | public-safe | Question bank for a first discovery call.                        |
| `discovery-call-notes.md`      | both     | next     | private     | Capture format used during/after the discovery call.             |
| `qualification-checklist.md`   | both     | planned  | public-safe | Decide pursue vs pass — fit, budget, authority, timing.          |
| `proposal.md`                  | project  | **built**| public-safe | Engagement proposal. *(Worked example.)*                         |
| `workshop-offer.md`            | workshop | next     | public-safe | Lightweight workshop proposal — shorter than a project proposal. |
| `sow.md`                       | both     | next     | private     | Statement of work — the contract.                                |
| `mutual-nda.md`                | both     | planned  | public-safe | Mutual NDA for pre-SOW conversations.                            |
| `ica-msa.md`                   | both     | planned  | public-safe | Independent contractor / master services agreement skeleton.     |
| `pricing-rationale.md`         | both     | next     | private     | Per-quote internal note: how we got to the number.               |
| `lost-deal-postmortem.md`      | both     | deferred | private     | Captured only when a quoted deal walks.                          |

## Kickoff & scoping

| Template                       | Type     | Status   | Publish     | Purpose                                                                                  |
| ------------------------------ | -------- | -------- | ----------- | ---------------------------------------------------------------------------------------- |
| `kickoff-agenda.md`            | both     | next     | public-safe | Run-sheet for the kickoff call.                                                          |
| `scoping.md`                   | project  | **built**| public-safe | Problem, goals, non-goals, constraints, risks. *(Lives in `engagements/_template/`.)*    |
| `access-checklist.md`          | both     | next     | public-safe | What we need from the client to start work (repo access, SSO, env, credentials).         |
| `communication-plan.md`        | both     | planned  | public-safe | Channels, cadences, response SLAs both directions.                                       |
| `risk-register.md`             | both     | planned  | public-safe | Running risk log — likelihood, impact, owner, mitigation, status.                        |
| `decision-log.md`              | both     | planned  | public-safe | Running record of decisions with dates and rationale.                                    |
| `assumptions-log.md`           | both     | planned  | public-safe | What we're assuming until proven otherwise — pairs with risk register.                   |

## Planning & estimation

| Template                       | Type     | Status   | Publish     | Purpose                                                                                   |
| ------------------------------ | -------- | -------- | ----------- | ----------------------------------------------------------------------------------------- |
| `estimation-worksheet.md`      | project  | next     | private     | Work breakdown × uncertainty bands × **agentic-leverage multiplier**. See note below.     |
| `capacity-plan.md`             | both     | next     | private     | Human-hours **and** token budget allocated across the engagement window.                  |
| `roadmap.md`                   | project  | planned  | public-safe | Milestone plan with target dates.                                                         |
| `definition-of-done.md`        | project  | planned  | public-safe | Acceptance criteria standard.                                                             |

> **The agentic-leverage angle is the one thing about resource planning that's unique to this practice.** Estimation and capacity templates explicitly track *human-hours* and *agent token spend* as parallel resources, not just one. The estimation worksheet should model the multiplier (the playbook from `/claude/playbooks/` we expect to apply) and the capacity plan should let `/command-center/token-burn/` roll up actuals against the budget per engagement.

## Execution & delivery

| Template                       | Type     | Status   | Publish     | Purpose                                                                                                                                  |
| ------------------------------ | -------- | -------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `status-report.md`             | both     | next     | public-safe | Weekly outcomes + outputs + next + risks + budget. **Promote** the inline stub from `engagements/_template/status/README.md` to a real template file. |
| `demo-script.md`               | project  | planned  | public-safe | Pre-demo run-sheet for stakeholder demos.                                                                                                |
| `change-request.md`            | project  | next     | public-safe | Capture scope change, impact (timeline / cost), and SOW delta to sign.                                                                   |
| `decision-record.md`           | project  | planned  | public-safe | Per-decision short record — context, options, choice, why. ADR-style.                                                                    |
| `issue-escalation.md`          | both     | planned  | public-safe | Memo format for raising a blocker to the client.                                                                                         |

## Close & handover

| Template                       | Type     | Status   | Publish     | Purpose                                                                                       |
| ------------------------------ | -------- | -------- | ----------- | --------------------------------------------------------------------------------------------- |
| `handover.md`                  | project  | next     | public-safe | Operational runbook for the client to own what we built.                                      |
| `retro.md`                     | both     | **built**| public-safe | Engagement retrospective. *(Lives in `engagements/_template/`.)* May be promoted to `/templates/` once shape stabilizes. |
| `invoice.md`                   | both     | planned  | private     | Markdown invoice — line items, totals, payment instructions.                                  |
| `testimonial-request.md`       | both     | planned  | public-safe | Email asking for a testimonial or reference permission.                                       |
| `case-study-internal.md`       | both     | planned  | private     | Internal write-up; later refined for `/consulting/case-studies/` when permission allows.      |

## Workshop / enablement (design + delivery)

| Template                       | Type     | Status   | Publish     | Purpose                                                                  |
| ------------------------------ | -------- | -------- | ----------- | ------------------------------------------------------------------------ |
| `curriculum-outline.md`        | workshop | next     | public-safe | Learning objectives → modules → time allocation.                         |
| `module-design.md`             | workshop | planned  | public-safe | Per module: objectives, demo, exercise, materials manifest.              |
| `prework-checklist.md`         | workshop | planned  | public-safe | What attendees do before showing up (accounts, installs, reading).       |
| `run-sheet.md`                 | workshop | next     | public-safe | Timeboxed minute-by-minute agenda for delivery day.                      |
| `facilitator-notes.md`         | workshop | planned  | public-safe | Cue cards for live delivery — transitions, prompts, watch-outs.          |
| `exercise-key.md`              | workshop | planned  | public-safe | Solution guide for each exercise.                                        |
| `attendee-feedback-survey.md`  | workshop | planned  | public-safe | Post-workshop survey — what worked, what didn't, NPS-style score.        |
| `workshop-retro.md`            | workshop | planned  | public-safe | Facilitator's own retro — what to change in v2.                          |

## Cross-cutting business ops

| Template                       | Type   | Status   | Publish | Purpose                                                                                                |
| ------------------------------ | ------ | -------- | ------- | ------------------------------------------------------------------------------------------------------ |
| `pipeline-ledger.md`           | cross  | planned  | private | Single markdown ledger — one row per prospect — stage, next step, $estimate, last-touch date.          |
| `weekly-capacity.md`           | cross  | planned  | private | Week sheet — hours sold vs hours available + token-spend budget across active engagements.             |
| `engagement-burn-rollup.md`    | cross  | planned  | private | Per-engagement rollup of human-hours + agent tokens vs budget. Feeds from `/command-center/token-burn/`. |
| `qbr.md`                       | cross  | deferred | private | Quarterly business review against own KPIs.                                                            |
| `reference-one-pager.md`       | cross  | deferred | public  | Portfolio one-pager sent to prospects.                                                                 |

## First-wave build order (when ready)

When the first real engagement starts (the `2026-internal-cc` self-engagement is a strong candidate), the templates marked **next** above are the minimum set to run the engagement end-to-end:

1. `discovery-call-notes.md` → 2. `pricing-rationale.md` → 3. `estimation-worksheet.md` → 4. `sow.md` → 5. `kickoff-agenda.md` → 6. `access-checklist.md` → 7. `capacity-plan.md` → 8. `status-report.md` → 9. `change-request.md` → 10. `handover.md`.

For the first workshop: `workshop-offer.md` → `curriculum-outline.md` → `run-sheet.md`. The remaining workshop templates can wait for workshop #2.

## Placeholder convention

Use `{{double-curly}}` markers. Common ones:

- `{{client}}` — client name.
- `{{date}}` — ISO date.
- `{{engagement_slug}}` — slug for the engagement (matches `/consulting/engagements/<year>-<slug>/`).
- `{{...}}` — anything else, named for what fills it.

Placeholders are documented in each template's frontmatter so future tooling can fill them programmatically.

## Frontmatter

```yaml
---
name: status-report
title: "Weekly status report"
placeholders:
  - client
  - date
  - engagement_slug
status: draft               # draft | active | retired
version: 0.1
created_at: 2026-06-15
updated_at: 2026-06-15
publish: public-safe        # public-safe | private (template structure; instances follow engagement sensitivity)
applies_to:
  engagement_types: [project, workshop]   # or [project] or [workshop]
---
```

`publish:` is informational — it tells a future "publish a snapshot of our methodology" job which templates can ship and which to redact.

## When to build a template

When you've handwritten the same document twice. Not before. A template forecloses on shape; if the shape isn't settled yet, a template ossifies the wrong thing. The catalog above is a *hypothesis* about which documents will recur — confirmation comes from doing the work.
