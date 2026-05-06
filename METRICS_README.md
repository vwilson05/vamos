# ADO Agent Metrics System (Python Implementation)

## Overview

The ADO Agent Metrics System provides comprehensive performance tracking and reporting for Azure DevOps teams. It generates clear, standardized metrics reports showing developer performance, impact, and achievements. **Fully implemented in Python** and integrated with the existing ADO agent.

## Key Features

- **Safe by Default**: All commands run in DRY-RUN mode unless explicitly overridden
- **Board-Based Metrics**: Uses ADO area paths and iteration paths (not generic "teams")
- **Multiple Output Formats**: HTML (with charts), Markdown, JSON
- **Developer Impact Analysis**: Tracks achievements and business value
- **Notification Support**: Slack and Teams integration (disabled by default)

## Setup

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Edit `.env` file with your ADO credentials:

```env
ADO_ORG_URL=https://dev.azure.com/your-org
ADO_PAT=your-personal-access-token
ADO_PROJECT=your-project

# Metrics defaults (optional)
METRICS_AREA_PATH=Data Platform\\Engineering
METRICS_ITERATION_PATH=Data Platform\\Ingestion Engineering Kanban
```

### 3. Configure Boards (Optional)

Edit `.ado-metrics.yml` to define your boards:

```yaml
boards:
  - name: "Ingestion Engineering"
    area_path: "Data Platform\\Engineering"
    iteration_path: "Data Platform\\Ingestion Engineering Kanban"
```

## Usage Examples

### Basic Commands (All DRY-RUN by default)

#### 1. Generate HTML Report
```bash
# Using environment variables (saves to metrics_reports/YYYY-MM-DD_board_name_metrics.html)
python cli.py metrics generate

# Using specific board (auto-saves with date)
python cli.py metrics generate --board "Ingestion Engineering"
# Creates: metrics_reports/2026-05-05_ingestion_engineering_metrics.html

# Custom output path
python cli.py metrics generate \
  --area-path "Data Platform\\Engineering" \
  --iteration-path "Data Platform\\Ingestion Engineering Kanban" \
  --output ./custom/my-report.html
```

#### 2. Preview Metrics in Terminal
```bash
# Quick preview - always dry-run
python cli.py metrics preview --board "Ingestion Engineering"
```

#### 3. Developer-Specific Metrics
```bash
python cli.py metrics developer "john.doe@company.com" \
  --area-path "Data Platform\\Engineering" \
  --iteration-path "Data Platform\\Ingestion Engineering Kanban"
```

#### 4. Export Raw Data
```bash
# Auto-saves to metrics_reports/YYYY-MM-DD_board_name_data.json
python cli.py metrics export --board "Ingestion Engineering"
# Creates: metrics_reports/2026-05-05_ingestion_engineering_data.json

# Custom output path
python cli.py metrics export \
  --board "Ingestion Engineering" \
  --output ./data/custom.json
```

#### 5. List Available Boards
```bash
# Show configured boards
python cli.py metrics boards
```

### Advanced Usage (Requires Explicit Confirmation)

#### Send to Slack (DANGEROUS - Requires Confirmation)
```bash
python cli.py metrics generate \
  --board "Ingestion Engineering" \
  --send slack \
  --no-dry-run

# You will be prompted:
# ⚠️  WARNING: You are about to send notifications!
# Type "yes" to confirm
```

## Metrics Included

### Performance Metrics
- **Work Items**: Open, Completed, Blocked, Past Due
- **Story Points**: Completed vs Committed
- **Velocity**: Trend over last 5 iterations
- **Bug Resolution**: Count and average resolution time
- **Cycle Time**: Average completion time

### Impact Analysis
- **Key Achievements**: High-impact deliverables
- **Customer Impact Score**: Based on customer-tagged items
- **Features Delivered**: Completed user stories
- **Bug Fixes**: Resolved bugs count

### Developer Breakdown
Each developer gets individual metrics:
- Stories completed this iteration
- Current workload (open items)
- Blocked items requiring attention
- Past due items
- Achievement highlights

## Report Formats

### HTML Report
- Beautiful, modern design with charts
- Interactive elements
- Print-friendly layout
- Mobile responsive

### Markdown Report
- Simple text format
- Great for documentation
- Easy to share via chat

### JSON Export
- Raw data for custom analysis
- Integration with other tools
- Archival purposes

## Safety Features

1. **DRY-RUN by Default**: No actions taken unless explicitly disabled
2. **Confirmation Required**: Dangerous actions require "yes" confirmation
3. **Test Commands**: Preview notifications without sending
4. **Local Reports**: Always saves locally before any external action

## Common Workflows

### Weekly Team Review
```bash
# Generate and review locally first
python cli.py metrics generate --board "Ingestion Engineering"

# Report is automatically saved with date:
# metrics_reports/2026-05-05_ingestion_engineering_metrics.html

# All reports are stored in metrics_reports/ folder for easy access
```

### Individual Performance Check
```bash
# Check your own metrics
python cli.py metrics developer "jimmycalvo.monge@halomd.com" \
  --board "Ingestion Engineering" \
  --include-achievements
```

### Executive Summary
```bash
# Generate comprehensive report with all details
python cli.py metrics generate \
  --board "Ingestion Engineering" \
  --format html \
  --include-charts \
  --include-achievements

# Auto-saved to: metrics_reports/2026-05-05_ingestion_engineering_metrics.html
# Charts and achievements are included by default
```

## Configuration File Reference

### .ado-metrics.yml
```yaml
boards:                        # Define your ADO boards
  - name: "Board Name"
    area_path: "Path\\To\\Area"
    iteration_path: "Path\\To\\Iteration"

metrics:
  always_dry_run: true         # Safety first
  require_confirmation: true   # Confirm dangerous actions

notifications:
  enabled: false              # Disabled by default
  slack:
    webhook_url: "${SLACK_WEBHOOK_URL}"
  teams:
    webhook_url: "${TEAMS_WEBHOOK_URL}"
```

## Troubleshooting

### No Metrics Found
- Verify area path and iteration path are correct
- Check that work items exist in the specified iteration
- Ensure PAT token has sufficient permissions

### Connection Issues
- Verify ADO_ORG_URL is correct (no trailing slash)
- Check PAT token is valid and not expired
- Ensure network connectivity to Azure DevOps

### Missing Data
- Some metrics require specific fields in work items
- Story points must be set for velocity calculations
- Target dates needed for "past due" calculations

## Best Practices

1. **Always Preview First**: Use `preview` command before generating reports
2. **Use Boards Config**: Define boards in `.ado-metrics.yml` for consistency
3. **Regular Cadence**: Run metrics weekly for trend analysis
4. **Archive Reports**: Keep historical reports for comparison
5. **Test Notifications**: Always test format before sending to team channels

## Future Enhancements

- Automated scheduling (cron/Task Scheduler)
- Custom metric definitions
- PR/Code review metrics integration
- Burndown/Burnup charts
- Sprint planning assistance
- Predictive analytics

## Support

For issues or feature requests, please contact your ADO administrator or submit feedback through your standard channels.