# ADO Board & Ticket Standards — Data Platform Engineering

> Source: https://halomd.atlassian.net/wiki/spaces/TP/pages/1181941836/ADO+Board+Ticket+Standards+Engineering
>
> Cached locally for use by `vamos reminders`. Re-sync this file when the
> Confluence page changes (no automated fetch yet — see TODO at the bottom).

## States we use

Only two states matter for in-flight work:

- **Active** — currently being worked on. One Active per engineer.
- **Blocked** — waiting on someone or something. Annotate with what.

Deprecated states (do not use): **QA**, **PR Ready**, **QA Ready**. Code Review
is automated by ADO when a PR is submitted — don't set it manually. Go straight
from Active → Closed when work is done.

## Daily comments

Every Active or Blocked ticket needs a comment from the assignee on the current
working day, posted by **5pm CST**. Even one line is fine:

- what you did today
- what's next
- any blockers

## Required fields on every story

- Assignee
- Story points (1 SP = 1 hour)
- Start date
- Target date

P1 tickets especially need a target date — leadership tracks them.

## Workbooks and closure

When you send the QA workbook to the BA, close the development ticket. If BA
feedback requires changes, open a **new** ticket for that follow-up work. We
don't reuse closed dev tickets for re-work.

## P1 / P2 / P3 priority handling

- **P1**: Highest priority. Must have target date. Aging in backlog is a red
  flag — pick these up first.
- **P2**: Default for most work.
- **P3**: Lowest priority. Can sit in backlog until P1/P2 work is clear.

## PRs & branches

- Every active PR must link to at least one ADO work item.
- Branch names follow `feature|bugfix|hotfix / <ticket-id> - <slug>`.
- When a PR merges, the linked ticket should move to Closed (with a resolution
  note in Notes / Resolution / System.Reason).

## Blocked tickets

Blocked > 5 days with no comment = stale. Either unblock (post who/what
you're waiting on) or escalate.

## Closing tickets

Closed tickets need a resolution note. "Fixed" is fine; the empty closure
loses information.

---

## TODO

- Wire up live fetch via Confluence API once `CONFLUENCE_TOKEN` is available
  in `.env`. For now, this file is the source of truth — update it manually
  when the page changes.
- The LLM-backed recommendation pass (v2 of `vamos reminders`, behind `--llm`)
  will use this file as system context.
