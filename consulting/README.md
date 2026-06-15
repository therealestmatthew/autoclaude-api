# /consulting/

The consulting & software-delivery business. The reusable IP and the operational history of engagements.

## Subdirs

- [methodologies/](methodologies/) — playbooks for delivery, discovery, estimation. The reusable *how* of the work. See its README for the planned-methodologies catalog.
- [templates/](templates/) — fillable templates (proposals, SOWs, status reports, retros). See its README for the **full template catalog** marked by status, type, and publishability.
- [positioning/](positioning/) — *(stub)* how we describe what we do.
- [offers/](offers/) — *(stub)* productized service offerings.
- [pricing/](pricing/) — *(stub)* pricing models and rationale.
- [case-studies/](case-studies/) — *(stub)* selected engagement write-ups for marketing.
- [engagements/](engagements/) — one folder per client engagement; `_template/` is the skeleton.

## Practice shape (current hypothesis)

- **Engagement archetypes:** fixed-scope project delivery + workshop / enablement. *(Audit and advisory-retainer offerings are out of scope until demand signals otherwise.)*
- **Staffing:** solo + agentic leverage. One human operator using the toolkit as force-multiplier; capacity planning is hours-of-one + token-budget, not RACI-across-humans.
- **Visibility:** repo is private. Templates and methodologies are flagged `public-safe` or `private` so a future "publish snapshot" pass knows what's shareable.
- **Origin:** designed from first principles (no legacy templates to absorb).

Changing any of these reshapes the template and methodology catalogs — revisit them when one changes.

## Stubs vs fleshed

In Phase 0 we ship real content for `methodologies/` (one worked example) and `templates/` (one worked example + the full catalog) and one-page stubs for the rest. Stubs exist so the *home* for that content is obvious before we have any of it. **Resist filling stubs with placeholder text** — better a stub that says "this is where positioning will live" than fake positioning copy that gets cited as if real.

## Relationship to /claude/

`/consulting/` is business-facing. `/claude/` is technical/operator-facing. A methodology may reference a `/claude/playbooks/` document for the technical delivery step — they're partners, not competitors.

## What this needs from other areas

To actually *deliver* engagements with the agentic-leverage angle (not just produce paper), `/claude/` and `/command-center/` will need specific artifacts. These are **not** to be built up front — they're a forward-looking inventory so when an engagement surfaces the need, the home is obvious.

### From `/claude/playbooks/`

| Playbook                          | Used during                                | Why                                                                                |
| --------------------------------- | ------------------------------------------ | ---------------------------------------------------------------------------------- |
| `engagement-kickoff`              | Sprint-zero                                | Standard sequence to set up a new engagement's environment, repo access, decision log, status cadence. |
| `greenfield-feature-delivery`     | Build phase (greenfield)                   | Already named in `claude/prompts/README.md` example. The default delivery playbook for new features. |
| `brownfield-codebase-onboarding`  | Sprint-zero (existing codebases)           | How to absorb a client's existing repo into our toolkit safely.                    |
| `weekly-status-drafting`          | Execution                                  | Pull from `/command-center/threads/`, git log, and the engagement folder → drafts a status report. |
| `workshop-content-build`          | Workshop design                            | Using the agentic toolkit to author and pressure-test workshop materials.          |
| `engagement-handover`             | Close                                      | Generate the handover runbook from the engagement folder's decisions and artifacts. |

### From `/claude/agents/`

| Agent                             | Purpose                                                                                              |
| --------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `scoping-interview-agent`         | Conversational partner during a discovery call — helps surface non-goals and unstated assumptions.   |
| `estimation-agent`                | Decomposes scope into a work-breakdown with uncertainty bands and the leverage multiplier.           |
| `status-drafter-agent`            | Reads thread logs + git history + engagement folder; drafts the weekly status report.                |
| `retro-facilitator-agent`         | Pulls the engagement record into a structured retro draft, including contributions-back-to-toolkit.  |
| `proposal-drafter-agent`          | Discovery-notes → proposal.md, in our voice.                                                         |

### From `/claude/skills/`

| Skill                             | Purpose                                                                                              |
| --------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `fill-template`                   | Generic: take a `{{placeholder}}`-marked template and a context bundle, produce the filled version.  |
| `redact-for-publish`              | Produce a public-safe version of an engagement artifact (strip client names, dollar amounts, secrets). |
| `engagement-status`               | Lightweight: from an engagement folder, surface "what's red, what's yellow, what's overdue."         |

### From `/command-center/`

| Surface                                          | What it gives                                                                                            |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| Pipeline view (over `templates/pipeline-ledger.md`) | One screen of "who's in the funnel, what stage, what's next."                                          |
| Engagement health view                           | Red/yellow/green per active engagement against status, burn, risks.                                      |
| Per-engagement burn rollup (`token-burn/`)       | Human-hours + agent-tokens vs the capacity plan. Closes the loop on the leverage hypothesis.             |
| Runbook: kick off a new engagement folder        | Operator runbook in `/command-center/runbooks/` — scaffolds `engagements/<year>-<slug>/` from `_template/`. |
| Runbook: close out an engagement                 | Operator runbook — drives retro draft, archives, optional case-study seed.                               |

These names are placeholders for shape, not commitments. Each gets built only when an engagement creates the actual need. The point of listing them here is so when you ask "what would it take to deliver engagements with leverage instead of just rebuilding consultancy hygiene?" the answer is on one page.
