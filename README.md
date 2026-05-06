# vamos

**HaloMD's agent suite.** A single CLI (`vamos`) plus a Streamlit UI that bundles every workflow agent the team uses:

| Subcommand | What it does | Who runs it |
|---|---|---|
| `vamos daily` | Personal daily-loop dispatcher (cron-friendly; runs sod/sync/eod automatically) | Each engineer, on their own laptop |
| `vamos sod` / `sync` / `eod` | Manual one-shots of the daily flow | Each engineer (cron also calls these under the hood) |
| `vamos metrics` | Backlog statistics report for project leadership | Team service host |
| `vamos healthcheck` | Per-developer ticket snapshot + team rollup | Team service host |
| `vamos hygiene` | Enforces ADO board standards (Jeff's spec) — report-only by default | Team service host (5pm CST cron) |
| `vamos pr-review [PR_ID]` | Reviews an Azure DevOps PR; `--watch` polls for new iterations | Engineer (ad-hoc) or team service (`--watch`) |
| `vamos ui` | Launches the Streamlit UI for non-technical users | Anyone |

The original `ado-agent` is now `vamos`'s personal-daily-flow. The dev still only manages the markdown file — everything else is automated.

## Three deployment shapes

vamos is one binary, three products. Pick the recipe that matches your role:

| Profile | Where it runs | What runs there | `.env` to use |
| --- | --- | --- | --- |
| **Personal** | Each engineer's laptop | `vamos daily` (cron) + ad-hoc `pr-review` | `.env` + `.env.personal` |
| **Team service** | One always-on host (or GitHub Actions) | `vamos metrics`, `healthcheck`, `hygiene`, `pr-review --watch` (cron, service PAT) | `.env` + `.env.team` |
| **On-demand** | Any laptop | Anything ad-hoc; `vamos ui` for non-techies | Whatever's local |

Profiles are layered: a base `.env` holds shared values; `.env.personal` or `.env.team` overlays profile-specific PATs and webhooks. Pick at runtime via `--profile personal|team` or `VAMOS_PROFILE=team`. Both example files ship in the repo.

## Quick start

```bash
git clone …  &&  cd ado-agent-v2
python3 -m venv .venv && source .venv/bin/activate
pip install -e .              # installs the `vamos` console script
pip install -e '.[ui]'         # add Streamlit for the UI

cp .env.example .env           # fill ADO_PAT, project, etc.
cp .env.personal.example .env.personal   # only on your own laptop
# (or)
cp .env.team.example .env.team           # only on the team service host

vamos test                     # confirms ADO auth
vamos daily --force sod        # try a one-shot
vamos hygiene --skip-post      # try the hygiene report
vamos ui                       # launch the UI on http://localhost:8501
```

## Flow (personal daily)

```
08:00  sod   → pulls assigned items, writes work/YYYY-MM-DD.md (sorted by priority)
              you edit the file all day: mark states, add notes, paste new requests
11:00  sync  → claude -p reads markdown vs ADO, posts comments / updates state /
              creates new tickets (any [NEW] sections get real IDs written back)
14:00  sync  → same
17:00  sync  → same
18:00  eod   → final sync + claude -p generates the "EOD:" summary + posts to Teams/Slack
```

A single scheduled job — `vamos daily` every 30 min — handles all five
phases. The dispatcher checks the time and what's already been done today, then
runs at most one of {sod, sync, eod} per fire. See [Scheduling](#scheduling).

## The team agents

These run on a single shared host (or as GitHub Actions). Each builds a single `TeamSnapshot` (one big WIQL query for the configured area path) and posts a Markdown report to your team's Teams or Slack channel.

| Agent | Schedule | What it produces |
| --- | --- | --- |
| `vamos metrics` | Weekly | Backlog statistics, throughput, aging — for project leadership |
| `vamos healthcheck` | Weekly | Per-developer ticket snapshot + team rollup |
| `vamos hygiene` | Daily 5pm CST | Enforces Jeff's ADO board standards. 7 rules: state discipline, daily-comments, required fields, PR linkage, branch naming, resolution-on-close, stale Blocked. Report-only by default; live-mode (`HYGIENE_LIVE_MODE=true` + `--auto-comment`) posts nudge comments on offending tickets. **Repo scope**: by default scans every repo in the project; limit via `HYGIENE_REPOS=a,b,c` in `.env` or `--repo` CLI flag (repeatable). |

Each agent caches its result to `state/<agent>/<YYYY-MM-DD>.json` so the UI can read it without re-querying ADO, and to `state/<agent>/logs/*.json` for audit.

## PR review

```
vamos pr-review              # if in a cloned repo: list PRs there
                             # else: list active PRs across ALL project repos
vamos pr-review 1234         # review PR 1234 — repo auto-detected (cwd) or
                             # auto-searched across all project repos if needed
vamos pr-review 1234 --no-post     # generate the review locally, don't post
vamos pr-review --repo halo-cooling 1234   # explicit repo (skips auto-search)
vamos pr-review --watch      # service mode: polls every project repo every 5 min,
                             # auto-reviews new iterations. State per-(repo,pr,iter).
```

The reviewer prompt lives at `prompts/pr_review/reviewer.md`. Comments are tagged with `<!-- vamos:pr-review -->` so re-runs don't double-post on the same iteration. Watch mode tracks per-PR iteration state in `state/pr-review/iterations.json`.

## Setup (one-time per developer)

1. Install Python 3.10+ and [Claude Code](https://docs.claude.com/claude-code).
2. Clone this repo and create a venv:
   ```
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   source .venv/bin/activate       # macOS/Linux
   pip install -r requirements.txt
   ```
3. Generate an ADO Personal Access Token at
   `https://dev.azure.com/<your-org>/_usersSettings/tokens` with **Work Items
   (Read, write, & manage)** scope.
4. Get webhook URLs from your admin:
   - **Teams webhook URL** - Your admin will provide this for Teams notifications
   - **Slack webhook URL** - Your admin will provide this for Slack notifications
   - You don't need to create these yourself; they're managed centrally

   **Note for Admins:**
   - For Teams setup, see the Workflows app configuration below
   - For Slack setup, see [SLACK_SETUP.md](./SLACK_SETUP.md)

5. Copy `.env.example` to `.env` and fill in the values:
   ```
   ADO_ORG_URL=https://dev.azure.com/halomd
   ADO_PROJECT=YourProject
   ADO_PAT=...                      # Your personal access token from step 3
   ADO_USER_EMAIL=                  # Leave blank for your own items
   ADO_READ_ONLY=true               # Start with true for safety!
   DEVELOPER_NAME=Your Name         # REQUIRED: Your full name for EOD posts
   CONNECTION_OPTION=Teams          # Choose "Teams" or "Slack"
   TEAMS_WEBHOOK_URL=...            # Get from admin (if using Teams)
   SLACK_WEBHOOK_URL=...            # Get from admin (if using Slack)
   ```
6. Smoke test:
   ```
   python cli.py test
   ```
   You should see your assigned items listed.

## Daily commands

```
python cli.py sod                  # start of day: writes work/YYYY-MM-DD.md
python cli.py sync --dry-run       # show what claude -p would do, no writes
python cli.py sync                 # apply changes to ADO
python cli.py eod --skip-post      # generate EOD text only, no Teams/Slack post
python cli.py eod                  # final sync + post to Teams/Slack (per CONNECTION_OPTION)
```

Useful flags:
- `--verbose` shows debug logs
- `--day 2026-04-25` operates on a back-dated markdown file
- `--force` (sod only) overwrites today's markdown

## The markdown file

Every section is a ticket. The HTML comment under the heading holds metadata:

```
## [12345] Fix SSO redirect loop
<!-- type: Bug | state: Active | priority: 2 | url: https://... -->

### Notes

Talked to QA — they think this is the new IdP redirect timeout.
Reproduced locally; root cause is the 30s session refresh, not the redirect.
```

What edits do what on the next sync:

| You do                                               | Sync does                                       |
| ---------------------------------------------------- | ----------------------------------------------- |
| Change `state: Active` → `state: Resolved`           | Transitions the ticket in ADO                   |
| Edit the title on the `## [12345]` line              | Updates `System.Title`                          |
| Type anything under `### Notes`                      | Posts as an ADO comment (idempotent by hash)    |
| Add a section `## [NEW] Refactor logging`            | Creates a new ticket per `templates/new-ticket.md` |
| Tag a heading `## [12345] [CLOSE] ...`               | Closes the ticket                               |
| Tag a heading `## [12345] [DELETE] ...`              | Removes the ticket                              |
| Paste a Teams/email message under a `### Notes` block | Posted as a comment with full context           |

### Customizing new-ticket conventions

`templates/new-ticket.md` defines what `[NEW]` tickets should look like —
default area path, title format, description sections, acceptance criteria
format, tag controlled list, priority defaults, predecessor linking rules.
Edit the file to match your team's conventions; the agent loads it on every
sync run, so changes apply on the next 30-min fire — no code change needed.

The `create` action that the LLM emits supports these fields per the template:
`area_path`, `iteration_path`, `acceptance_criteria`, `tags`, `parent_id`, and
a `links` array with `rel` values like `System.LinkTypes.Dependency-Reverse`
(blocked-by) or `System.LinkTypes.Related`. If the markdown context doesn't
provide enough info for a field, the model omits it and ADO uses its default —
no fabrication.

Notes are deduplicated by SHA-256 hash, so re-running sync is safe — a comment
won't be posted twice. Sidecar state lives in `state/YYYY-MM-DD.json`; every
sync run also drops a full audit log in `state/logs/`.

## Scheduling

You have two approaches for automating the ado-agent:

### Option 1: Single Dispatcher (Recommended)

A single command — `python cli.py daily` — figures out what to do based on the
time of day and what's already been done today. Schedule it to fire every 30
minutes; the dispatcher chooses one of `sod`, `sync`, `eod`, or no-op:

| Condition                                                    | Action       |
| ------------------------------------------------------------ | ------------ |
| Weekend (and `RUN_SKIP_WEEKENDS=true`)                       | skip         |
| First run at/after `RUN_SOD_AT` (default 08:00) for the day  | `sod`        |
| At/after `RUN_EOD_AT` (default 18:00) and EOD not done       | `eod`        |
| Between SOD and EOD, ≥ `RUN_SYNC_INTERVAL_MIN` min since last | `sync`       |
| Otherwise                                                    | no-op        |

Run state is tracked in `state/<date>-run.json`, so missed runs catch up on
the next fire (e.g. laptop closed all morning → 13:00 fire still does SOD).

Override the schedule via env vars in `.env`:
```
RUN_SOD_AT=08:00
RUN_EOD_AT=18:00
RUN_SYNC_INTERVAL_MIN=180
RUN_SKIP_WEEKENDS=true
```

### Option 2: Separate Tasks for Each Command

Alternatively, you can create separate scheduled tasks for SOD, SYNC, and EOD.
This gives you more granular control over each operation.

### Windows Task Scheduler Setup

#### GUI Method (Separate Tasks)

Create three separate tasks in Task Scheduler:

**1. SOD Task (Start of Day)**
- **General Tab:**
  - Name: `ADO Agent - Start of Day`
  - Run only when user is logged on (for Halo VMs)
- **Triggers Tab:**
  - Daily at 8:00 AM
  - Enabled
- **Actions Tab:**
  - Action: Start a program
  - Program/script: `C:\Users\[YourUsername]\AppData\Local\Programs\Python\Python312\python.exe`
  - Add arguments: `cli.py sod`
  - Start in: `C:\Users\[YourUsername]\OneDrive - HALOMD\Desktop\ado-agent`

**2. SYNC Task (Hourly Sync)**
- **General Tab:**
  - Name: `ADO Agent - Hourly Sync`
  - Run only when user is logged on
- **Triggers Tab:**
  - Daily at 9:00 AM
  - Repeat task every: 1 hour
  - For a duration of: 8 hours
  - Enabled
- **Actions Tab:**
  - Action: Start a program
  - Program/script: `C:\Users\[YourUsername]\AppData\Local\Programs\Python\Python312\python.exe`
  - Add arguments: `cli.py sync`
  - Start in: `C:\Users\[YourUsername]\OneDrive - HALOMD\Desktop\ado-agent`

**3. EOD Task (End of Day)**
- **General Tab:**
  - Name: `ADO Agent - End of Day`
  - Run only when user is logged on
- **Triggers Tab:**
  - Daily at 4:00 PM (or 6:00 PM)
  - Enabled
- **Actions Tab:**
  - Action: Start a program
  - Program/script: `C:\Users\[YourUsername]\AppData\Local\Programs\Python\Python312\python.exe`
  - Add arguments: `cli.py eod --skip-sync`
  - Start in: `C:\Users\[YourUsername]\OneDrive - HALOMD\Desktop\ado-agent`

**Note:** Halo Virtual Machines do not support the "Run whether user is logged on or not" option,
so tasks will only run when you're logged into the VM.

#### PowerShell Method (Single Dispatcher)

```powershell
$AdoAgent = "C:\path\to\ado-agent"
$Python   = "$AdoAgent\.venv\Scripts\python.exe"

$action  = New-ScheduledTaskAction -Execute $Python `
            -Argument "$AdoAgent\cli.py daily" -WorkingDirectory $AdoAgent
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(7) `
            -RepetitionInterval (New-TimeSpan -Minutes 30) `
            -RepetitionDuration (New-TimeSpan -Hours 13)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
            -RunOnlyIfNetworkAvailable -DontStopIfGoingOnBatteries `
            -AllowStartIfOnBatteries

Register-ScheduledTask -TaskName "ado-agent" `
    -Action $action -Trigger $trigger -Settings $settings `
    -RunLevel Highest -Force
```

`StartWhenAvailable` is the catch-up flag — if the VDI was off at the trigger
time, Task Scheduler runs the next time it boots.

### macOS Cron Setup (Runs Without Login)

macOS can run scheduled tasks even when you're not logged in using cron or launchd.

#### Option A: Cron (Traditional)

1. **Open your crontab for editing:**
   ```bash
   crontab -e
   ```

2. **Add entries for separate tasks:**
   ```bash
   # ADO Agent Schedule
   # Environment setup
   PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin

   # Start of Day - 8:00 AM weekdays
   0 8 * * 1-5 cd /path/to/ado-agent && /path/to/ado-agent/.venv/bin/python cli.py sod >> logs/sod.log 2>&1

   # Hourly Sync - Every hour from 9 AM to 5 PM weekdays
   0 9-17 * * 1-5 cd /path/to/ado-agent && /path/to/ado-agent/.venv/bin/python cli.py sync >> logs/sync.log 2>&1

   # End of Day - 6:00 PM weekdays
   0 18 * * 1-5 cd /path/to/ado-agent && /path/to/ado-agent/.venv/bin/python cli.py eod >> logs/eod.log 2>&1
   ```

3. **Or use single dispatcher approach:**
   ```bash
   # Run every 30 minutes on weekdays
   */30 * * * 1-5 cd /path/to/ado-agent && /path/to/ado-agent/.venv/bin/python cli.py daily >> logs/run.log 2>&1
   ```

4. **Grant cron Full Disk Access (macOS 10.14+):**
   - System Preferences → Security & Privacy → Privacy → Full Disk Access
   - Click the lock and authenticate
   - Click + and add `/usr/sbin/cron`

#### Option B: Launchd (macOS Native - Recommended)

Launchd is more reliable and provides better control than cron on macOS.

1. **Create a plist file:** `~/Library/LaunchAgents/com.halomd.ado-agent.plist`

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
     "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.halomd.ado-agent</string>

       <key>ProgramArguments</key>
       <array>
           <string>/path/to/ado-agent/.venv/bin/python</string>
           <string>/path/to/ado-agent/cli.py</string>
           <string>run</string>
       </array>

       <key>WorkingDirectory</key>
       <string>/path/to/ado-agent</string>

       <key>StartCalendarInterval</key>
       <array>
           <!-- Run every 30 minutes from 7 AM to 7 PM on weekdays -->
           <dict>
               <key>Weekday</key>
               <integer>1</integer>
               <key>Hour</key>
               <integer>7</integer>
               <key>Minute</key>
               <integer>0</integer>
           </dict>
           <dict>
               <key>Weekday</key>
               <integer>1</integer>
               <key>Hour</key>
               <integer>7</integer>
               <key>Minute</key>
               <integer>30</integer>
           </dict>
           <!-- Continue pattern for all times... -->
           <!-- Or use a separate script that runs every 30 min -->
       </array>

       <key>StandardOutPath</key>
       <string>/path/to/ado-agent/logs/launchd.log</string>

       <key>StandardErrorPath</key>
       <string>/path/to/ado-agent/logs/launchd.error.log</string>

       <key>RunAtLoad</key>
       <false/>
   </dict>
   </plist>
   ```

2. **Load the launch agent:**
   ```bash
   launchctl load ~/Library/LaunchAgents/com.halomd.ado-agent.plist
   ```

3. **To run without being logged in**, move the plist to system level:
   ```bash
   sudo cp ~/Library/LaunchAgents/com.halomd.ado-agent.plist /Library/LaunchDaemons/
   sudo launchctl load /Library/LaunchDaemons/com.halomd.ado-agent.plist
   ```

4. **Verify it's running:**
   ```bash
   launchctl list | grep halomd
   ```

5. **To unload/stop:**
   ```bash
   launchctl unload /Library/LaunchDaemons/com.halomd.ado-agent.plist
   ```

**Important Notes for macOS:**
- Ensure your `.env` file has absolute paths for `WORK_DIR` and `STATE_DIR`
- The Python virtual environment must use absolute paths
- Grant Terminal/Python Full Disk Access if accessing protected directories
- Launchd jobs run with limited environment variables, so specify full paths

To force a specific phase manually:
```
python cli.py daily --force sod
python cli.py daily --force sync
python cli.py daily --force eod
```

## Safe rollout

1. Set `ADO_READ_ONLY=true` for the first day. Only `sod` (read) and dry-run
   `sync --dry-run` work; the action log will show what *would* have changed.
2. Set `ADO_USER_EMAIL=teammate@halomd.com` to test against someone else's
   queue without writing.
3. Once confident, set `ADO_READ_ONLY=false` and unset `ADO_USER_EMAIL`.
4. Watch the first few real syncs in `state/logs/` — every action is recorded
   with the full prompt and response.

## Troubleshooting

- **`claude` not on PATH** → set `CLAUDE_BIN` in `.env` to the full path.
- **401 from ADO** → PAT expired or wrong scope. Regenerate with Work Items R/W.
- **Sync did nothing** → check `state/logs/<day>-sync-*.json` — the LLM may have
  judged everything already in sync. Run with `--verbose` to see the prompt size.
- **Comment posted twice** → shouldn't happen (hashes are tracked) but if it
  does, delete the entry from `state/<day>.json` to reset.
- **Teams post fails with 405** → your URL is not a webhook. The most common
  mistake is pasting a Teams deep-link (`teams.cloud.microsoft/l/chat/...`)
  copied from "copy link" on a chat — those don't accept POSTs. Set up a
  Workflows webhook (see step 4 above) and use that URL instead.
- **Teams post fails with other errors** → `vamos/teams.py` auto-detects
  Workflows (`*.logic.azure.com`) vs legacy (`*.webhook.office.com`) and sends
  the right payload schema. If your tenant routes through a different host,
  open the file and adjust `LEGACY_HOSTS`.

## For project leadership (non-technical quickstart)

You don't need a terminal. Ask engineering for the link to the team's Streamlit instance, or run on your laptop:

1. Have someone install vamos for you (or follow [Quick start](#quick-start)).
2. Open a terminal and run: `vamos ui`
3. Open `http://localhost:8501` in your browser.
4. **Team status** page → click **Run hygiene now** or **Run healthcheck now**, read the report, click **Post to Teams/Slack** when ready (gated by a confirm checkbox so nothing posts by accident).

Reports are cached for the day — opening the page doesn't re-query ADO until you click Run.

## Adding a new hygiene rule

Each rule is a single Python file under `vamos/hygiene/rules/` exporting:

```python
RULE_ID = "my-rule"

def check(snapshot, cfg) -> list[Finding]:
    return [...]
```

Then add `(RULE_ID, my_rule.check)` to `ALL_RULES` in `vamos/hygiene/rules/__init__.py`. Done — no other plumbing.

The `TeamSnapshot` (`vamos.core.snapshot`) gives you the team's work items, comments on Active/Blocked items, and PRs from configured repos, all loaded with one round-trip per resource. Don't re-query ADO from inside a rule; the snapshot has what you need.

## Admin Guide: Webhook Setup

### Microsoft Teams Webhook Setup
The legacy "Incoming Webhook" connector is deprecated; use the **Workflows** app:
1. Teams → search **Workflows** → **+ New flow**
2. Template: **"Post to a channel when a webhook request is received"**
3. Pick a channel (private channels work; DMs are not supported)
4. Save → copy the generated URL (looks like `https://prod-XX.<region>.logic.azure.com:443/workflows/.../`)
5. Share this URL with your developers for their `.env` configuration

**Note:** Teams deep-links (`teams.cloud.microsoft/l/chat/...`) are NOT webhooks.

### Slack Webhook Setup
See [SLACK_SETUP.md](./SLACK_SETUP.md) for detailed Slack webhook configuration.
Share the resulting webhook URL with your developers.
