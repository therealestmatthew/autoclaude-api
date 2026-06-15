# /consulting/methodologies/

The reusable *how* of the consulting work. Each methodology is a markdown document describing a repeatable practice — discovery, delivery, estimation, status cadence, etc.

## Files

- [delivery.md](delivery.md) — how we run a delivery engagement end-to-end. *(Worked example, v0.1 draft.)*

## Planned methodologies

The practice targets **fixed-scope project delivery** and **workshop / enablement**. The following methodologies are the ones we know we'll codify, but per the rule below, **don't pre-write them** — wait until each has been used on two engagements.

| Methodology              | Applies to | Why it's likely needed                                                                                                  |
| ------------------------ | ---------- | ----------------------------------------------------------------------------------------------------------------------- |
| `delivery.md`            | project    | Sprint-zero → build → stabilize → close. **Built (v0.1 draft).**                                                        |
| `discovery.md`           | both       | How we run a discovery call → scoping.md. Covers question structure, listening posture, the gap between client framing and our interpretation. |
| `estimation.md`          | project    | How we estimate work *including the agentic-leverage multiplier*. Distinguishes human-hours from token-spend and models uncertainty bands. |
| `pricing.md`             | both       | How we *decide* a price (value, leverage, downside risk). The rate card itself lives in `/consulting/pricing/`, private. |
| `workshop-design.md`     | workshop   | Curriculum-as-product methodology — outcome-driven module design, exercise design, materials hygiene.                   |
| `engagement-management.md` | both     | Cadence, communications, status discipline, change-request handling, escalation paths.                                  |

## When to add a methodology

When you find yourself repeating an approach across two engagements and want to codify it. **Don't pre-write methodologies you haven't actually used** — premature codification is more work to unwind than to write fresh.

The list above is a *hypothesis* about what we'll need, not a backlog to grind through. If a planned methodology never gets used, delete the row.

## Frontmatter

```yaml
---
name: delivery
title: "Delivery methodology"
applies_to:
  engagement_types: [project, workshop]   # or [project] or [workshop]
status: active            # active | draft | retired
version: 0.1
created_at: 2026-06-14
updated_at: 2026-06-14
---
```

## Relationship to other areas

- A methodology may reference a `/claude/playbooks/` doc for the technical delivery step (e.g., `delivery.md` § Build references `greenfield-feature-delivery` playbook).
- A methodology lists which `/consulting/templates/` it uses at each phase.
- The methodology stays *generic* — engagement-specific tailoring lives in `/consulting/engagements/<year>-<client>/methodology.md` (copied from here and adapted).
