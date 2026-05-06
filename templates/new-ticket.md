# New ticket creation guidelines

These rules apply ONLY to `create` actions for `[NEW]` markdown sections.
Edit this file to match your team's conventions — the sync agent reads it on
every run, so changes apply immediately, no code change needed.

If a field's value can't be confidently inferred from the markdown, OMIT it
and let ADO use its default. Don't fabricate.

## Default placement

- **Area Path**: `Data Platform` (set the `area_path` field)
- **Iteration Path**: omit — let ADO triage assign the current sprint
- **Default work item type**: `User Story`. Use `Bug` only for defects with
  reproduction steps. Use `Task` only for sub-work under an existing story.

## Title format

- Short imperative phrase, ≤ 80 chars.
- Lead with a verb: "Add", "Refactor", "Fix", "Investigate", "Remove".
- Do NOT include ticket numbers in the title (use `links` instead).
- Customer-specific work: include the customer name (e.g. "Fix VITUITY EOB
  generation timeout"). Cross-customer work: omit customer.

## Description format

Plain text. Use exactly these three subsections, in this order:

```
**Context**
Why this work exists, what triggered it (1–3 sentences). If it came from
another ticket, mention the ticket ID here.

**Outcome**
What "done" looks like in one or two sentences. The reader should be able
to verify completion from this paragraph alone.

**Notes**
Any pointers, links, caveats, related investigations.
```

## Acceptance criteria

For `User Story` and `Feature` types, ALWAYS populate `acceptance_criteria`.
For `Task` and `Bug`, populate when the markdown has enough detail to do so.

Format: bulleted list, each bullet independently verifiable. Use this exact
HTML so it renders correctly in ADO:

```html
<ul>
  <li>Snowflake TASK created in DEV and PROD</li>
  <li>Alert fires within 15 minutes of staleness > 4h</li>
  <li>Page routes to data-platform-oncall</li>
</ul>
```

## Linking

When the new ticket arose from work on existing tickets in the markdown, add
the appropriate links:

| Relationship                              | `rel` value                              |
| ----------------------------------------- | ---------------------------------------- |
| Caused by / blocked by an earlier ticket | `System.LinkTypes.Dependency-Reverse`    |
| Will block a downstream ticket            | `System.LinkTypes.Dependency-Forward`    |
| Related, no causal order                  | `System.LinkTypes.Related`               |
| Parent feature / epic                     | use `parent_id` (NOT `links`)            |

Use the `links` array of the `create` action; the harness emits the link
calls right after the create succeeds.

## Tags

Apply tags from this controlled list (use `tags` as an array of strings):

- `EDI` — anything touching 837 / 835 / 270 / 271 pipelines
- `snowflake` — Snowflake-specific work
- `dbt` — dbt model / pipeline work
- `prod-support` — production firefighting
- `tech-debt` — refactoring / cleanup
- `monitoring` — alerting / observability
- Customer codes when work is customer-specific: `Northstar`, `SAOT`,
  `VITUITY`, `AEMA`, `Prestige`, `GoRev`, etc.

## Priority

- `1` — production blocker, customer-facing outage
- `2` — active customer ticket or sprint commitment
- `3` — planned work, tech debt, near-term backlog (default)
- `4` — nice-to-have, exploratory

If unclear, default to `3`.
