"""
Report generator for ADO metrics
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from .types import BoardMetrics, ReportOptions, ReportResult

log = logging.getLogger(__name__)


class ReportGenerator:
    """Generate formatted reports from collected metrics"""

    def generate_report(self, metrics: BoardMetrics, options: ReportOptions) -> ReportResult:
        """Generate a metrics report in the requested format"""
        log.info(f"Generating {options.format} report for {metrics.board}")

        # Create output directory if needed
        output_path = Path(options.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate report based on format
        if options.format == 'html':
            content = self._generate_html(metrics, options)
        elif options.format == 'markdown':
            content = self._generate_markdown(metrics, options)
        elif options.format == 'json':
            content = self._generate_json(metrics, options)
        else:
            raise ValueError(f"Unsupported format: {options.format}")

        # Save report to file
        output_path.write_text(content, encoding='utf-8')

        # Handle notifications if enabled (always dry-run for now)
        notifications = []
        if options.send_notifications and not options.dry_run:
            log.warning("Notifications requested but not implemented yet")

        return ReportResult(
            report=content,
            local_path=str(output_path),
            notifications=notifications
        )

    def _generate_html(self, metrics: BoardMetrics, options: ReportOptions) -> str:
        """Generate HTML report with beautiful CSS styling"""

        # Calculate team totals for the week
        week_total = sum(dev.performance.user_stories.completed_this_iteration for dev in metrics.developers)
        blocked_total = sum(dev.performance.user_stories.blocked for dev in metrics.developers)
        past_due_total = sum(dev.performance.user_stories.past_due for dev in metrics.developers)

        # Generate developer cards with enhanced metrics
        developer_cards = []
        for dev in metrics.developers:
            perf = dev.performance

            # Calculate metrics
            if perf.story_points.committed > 0:
                completion_pct = int((perf.story_points.completed / perf.story_points.committed) * 100)
            else:
                completion_pct = 0

            # Productivity score (simple calculation based on completed items)
            productivity_score = perf.user_stories.completed_this_iteration * 10

            # Determine status and badges - only show issues, no comparisons
            badges = []
            if perf.user_stories.blocked > 0:
                badges.append(f'<span class="badge badge-warning"> ️ {perf.user_stories.blocked} Blocked</span>')
            if perf.user_stories.past_due > 0:
                badges.append(f'<span class="badge badge-danger">⏰ {perf.user_stories.past_due} Overdue</span>')

            badges_html = ' '.join(badges) if badges else '<span class="badge badge-neutral"> Active</span>'

            # Main Completed Tickets - show what they actually delivered
            achievements_html = ""
            if options.include_achievements and dev.impact.key_achievements:
                achievement_items = []
                achievements_html = f'<div class="completed-tickets-section"><div class="section-title"> Completed This Week</div><ul class="achievements">'
                for i, achievement in enumerate(dev.impact.key_achievements[:5], 1):
                    achievement_items.append(f'<li>{achievement.title}</li>')
                achievements_html += "".join(achievement_items) + '</ul></div>'

            # Trend indicator (mock data for now)
            trend = "↗️" if perf.user_stories.completed_this_iteration > 2 else "→" if perf.user_stories.completed_this_iteration > 0 else "↘️"

            developer_cards.append(f"""
            <div class="dev-card">
                <div class="dev-header">
                    <h3 class="dev-name">{dev.developer.display_name}</h3>
                    <div class="dev-badges">{badges_html}</div>
                </div>

                <div class="progress-section">
                    <div class="progress-bar-container">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width:{completion_pct}%;background:{'#10b981' if completion_pct >= 80 else '#f59e0b' if completion_pct >= 60 else '#ef4444'}"></div>
                        </div>
                        <span class="progress-label">{completion_pct}% of {perf.story_points.committed} pts</span>
                    </div>
                </div>

                <div class="kpi-row">
                    <div class="kpi">
                        <div class="lbl">Active Tickets</div>
                        <div class="val blue">{perf.user_stories.open + perf.tasks.in_progress}</div>
                    </div>
                    <div class="kpi">
                        <div class="lbl">Closed This Week</div>
                        <div class="val green">{perf.user_stories.completed_this_iteration}</div>
                    </div>
                    <div class="kpi">
                        <div class="lbl">Blocked</div>
                        <div class="val {'red' if perf.user_stories.blocked > 0 else 'cyan'}">{perf.user_stories.blocked}</div>
                    </div>
                </div>

                <div class="story-points-summary">
                    <div class="sp-row">
                        <span class="sp-label"> Story Points (Closed This Week):</span>
                        <span class="sp-value-large">{int(perf.story_points.completed)}</span>
                    </div>
                    <div class="sp-row">
                        <span class="sp-label"> Story Points (Currently Active):</span>
                        <span class="sp-value-large">{int(perf.story_points.committed - perf.story_points.completed)}</span>
                    </div>
                </div>

                {achievements_html}

                <div class="dev-footer">
                    <span class="productivity-score" title="Productivity Score">
                        Score: <strong>{productivity_score}</strong>
                    </span>
                    <span class="last-updated">
                        Updated: {datetime.now().strftime('%H:%M')}
                    </span>
                </div>
            </div>
            """)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Developer Performance Dashboard - {metrics.board}</title>
    <style>
        {self._get_css_styles()}
    </style>
</head>
<body>
    <div class="wrap">
        <header>
            <h1>Developer Performance Dashboard</h1>
            <p class="sub">Generated {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} • Last 7 days • {len(metrics.developers)} developers • {metrics.iteration_path.split('\\')[-1]}</p>
        </header>

        <!-- Summary KPIs -->
        <div class="kpi-row">
            <div class="kpi">
                <div class="lbl">Stories This Week</div>
                <div class="val blue">{week_total}</div>
            </div>
            <div class="kpi">
                <div class="lbl">Total Blocked</div>
                <div class="val {'red' if blocked_total > 0 else 'green'}">{blocked_total}</div>
            </div>
            <div class="kpi">
                <div class="lbl">Active Developers</div>
                <div class="val purple">{len(metrics.developers)}</div>
            </div>
            <div class="kpi">
                <div class="lbl">Avg Per Developer</div>
                <div class="val cyan">{week_total / len(metrics.developers) if metrics.developers else 0:.1f}</div>
            </div>
        </div>

        <div class="divider"></div>

        <!-- Developer Cards -->
        <div class="developers-section">
            <h2 class="section-title"> Individual Performance</h2>
            <div class="dev-grid">
                {"".join(developer_cards)}
            </div>
        </div>

        <footer>
            Generated {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} • Last 7 days • {'DRY RUN MODE' if options.dry_run else 'Production Mode'} • ADO Metrics v1.0.0
        </footer>
    </div>
</body>
</html>"""
        return html

    def _get_css_styles(self) -> str:
        """Get CSS styles for the HTML report"""
        return """
        :root {
            --bg:#f8f9fb;
            --surface:#ffffff;
            --card:#ffffff;
            --border:#e2e5ea;
            --text:#1a1d23;
            --muted:#6b7280;
            --accent:#2563eb;
            --blue:#2563eb;
            --purple:#7c3aed;
            --green:#16a34a;
            --red:#dc2626;
            --orange:#ea580c;
            --cyan:#0891b2;
            --pink:#db2777;
            --shadow:0 1px 3px rgba(0,0,0,0.06),0 1px 2px rgba(0,0,0,0.04);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }

        .wrap {
            max-width: 1440px;
            margin: 0 auto;
            padding: 32px 24px;
        }

        .dashboard {
            max-width: 1440px;
            margin: 0 auto;
            padding: 32px 24px;
        }

        /* Header */
        header {
            margin-bottom: 32px;
        }

        h1 {
            font-size: 28px;
            font-weight: 700;
            color: var(--text);
            margin-bottom: 2px;
        }

        .sub {
            color: var(--muted);
            font-size: 13px;
        }

        .header-subtitle {
            color: var(--muted);
            font-size: 13px;
        }

        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .header-stats {
            display: flex;
            gap: 2rem;
        }

        .header-stat {
            text-align: center;
        }

        .header-stat.warning .stat-value {
            color: var(--orange);
        }

        .stat-value {
            display: block;
            font-size: 28px;
            font-weight: 800;
            color: var(--accent);
        }

        .stat-label {
            display: block;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: .6px;
            color: var(--muted);
            margin-top: 4px;
        }

        /* Highlights Section */
        .highlights-section {
            margin-bottom: 2rem;
        }

        .section-title, .section-hdr {
            font-size: 18px;
            font-weight: 700;
            margin-bottom: 4px;
            display: flex;
            align-items: center;
            gap: 10px;
            color: var(--text);
        }

        .divider {
            border: none;
            border-top: 1px solid var(--border);
            margin: 28px 0;
        }

        .highlights-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
        }

        .highlight-card {
            background: var(--card);
            border-radius: 12px;
            padding: 1.5rem;
            display: flex;
            gap: 1rem;
            align-items: center;
            border: 1px solid var(--border);
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .highlight-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.3);
        }

        .highlight-card.star {
            background: linear-gradient(135deg, rgba(129, 140, 248, 0.1) 0%, rgba(34, 211, 238, 0.1) 100%);
            border-color: var(--accent);
        }

        .highlight-card.warning {
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(239, 68, 68, 0.1) 100%);
            border-color: var(--warning);
        }

        .highlight-icon {
            font-size: 2rem;
        }

        .highlight-title {
            font-size: 0.875rem;
            color: var(--muted);
            margin-bottom: 0.25rem;
        }

        .highlight-value {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text);
        }

        .highlight-detail {
            font-size: 0.875rem;
            color: var(--muted);
        }

        /* Developer Grid */
        .dev-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
            gap: 14px;
            margin-bottom: 24px;
        }

        .card, .dev-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px;
            box-shadow: var(--shadow);
        }

        .dev-card h3 {
            font-size: 15px;
            color: var(--accent);
            margin-bottom: 10px;
            font-weight: 600;
        }

        .dev-header {
            margin-bottom: 1rem;
        }

        .dev-name {
            font-size: 1.125rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: var(--text);
        }

        .dev-badges {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }

        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 5px;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .3px;
        }

        .badge-star {
            background: rgba(37,99,235,.08);
            color: var(--blue);
        }

        .badge-warning {
            background: rgba(234,88,12,.08);
            color: var(--orange);
        }

        .badge-danger {
            background: rgba(220,38,38,.08);
            color: var(--red);
        }

        .badge-success {
            background: rgba(22,163,74,.08);
            color: var(--green);
        }

        .badge-neutral {
            background: rgba(107,114,128,.08);
            color: var(--muted);
        }

        /* Progress Section */
        .progress-section {
            margin-bottom: 1rem;
        }

        .progress-bar-container {
            position: relative;
        }

        .progress-bar {
            height: 8px;
            background: var(--surface);
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 0.5rem;
        }

        .progress-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s;
        }

        .progress-label {
            font-size: 0.75rem;
            color: var(--muted);
        }

        /* Metrics Grid - KPI Style */
        .metrics-grid, .kpi-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 10px;
            margin-bottom: 20px;
        }

        .metric-box, .kpi {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px 14px;
            box-shadow: var(--shadow);
            display: flex;
            align-items: center;
            gap: 0.5rem;
            position: relative;
        }

        .metric-box.primary {
            border-left: 3px solid var(--blue);
        }

        .metric-box.alert {
            border-left: 3px solid var(--red);
        }

        .metric-content {
            flex: 1;
        }

        .metric-value, .kpi .val {
            font-size: 28px;
            font-weight: 800;
            line-height: 1.1;
            color: var(--text);
        }

        .metric-value.blue { color: var(--blue); }
        .metric-value.green { color: var(--green); }
        .metric-value.red { color: var(--red); }
        .metric-value.orange { color: var(--orange); }

        .metric-label, .kpi .lbl {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: .6px;
            color: var(--muted);
            margin-bottom: 4px;
        }

        .metric-icon {
            display: none;
        }

        .metric-trend {
            position: absolute;
            top: 14px;
            right: 14px;
            font-size: 1rem;
            opacity: 0.6;
        }

        /* Story Points Summary */
        .story-points-summary {
            background: var(--surface);
            border-radius: 8px;
            padding: 0.75rem;
            margin-bottom: 1rem;
            border-left: 3px solid var(--accent);
        }

        .sp-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem 0;
        }

        .sp-row:not(:last-child) {
            border-bottom: 1px solid var(--border);
        }

        .sp-label {
            font-size: 0.875rem;
            color: var(--muted);
        }

        .sp-value-large {
            font-size: 20px;
            font-weight: 700;
            color: var(--accent);
        }

        .kpi .lbl {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: .6px;
            color: var(--muted);
            margin-bottom: 4px;
        }

        .kpi .val {
            font-size: 28px;
            font-weight: 800;
            line-height: 1.1;
        }

        .kpi .val.blue { color: var(--blue); }
        .kpi .val.purple { color: var(--purple); }
        .kpi .val.green { color: var(--green); }
        .kpi .val.red { color: var(--red); }
        .kpi .val.orange { color: var(--orange); }
        .kpi .val.cyan { color: var(--cyan); }
        .kpi .val.accent { color: var(--accent); }
        .kpi .val.pink { color: var(--pink); }

        /* Completed Tickets Section */
        .completed-tickets-section {
            margin-top: 1rem;
            padding: 1rem;
            background: var(--surface);
            border-radius: 8px;
            border-left: 3px solid var(--success);
        }

        .section-title {
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--muted);
            margin-bottom: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        /* Achievements/Tickets List */
        .achievements {
            list-style: none;
            margin: 0;
            padding: 0;
            font-size: 0.875rem;
        }

        .achievements li {
            margin-bottom: 0.5rem;
            color: var(--text);
            position: relative;
            padding-left: 1.25rem;
        }

        .achievements li::before {
            content: " ";
            position: absolute;
            left: 0;
            color: var(--success);
            font-weight: bold;
        }

        .achievements li:last-child {
            margin-bottom: 0;
        }

        /* Footer */
        .dev-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
            font-size: 0.875rem;
            color: var(--muted);
        }

        .productivity-score strong {
            color: var(--accent);
        }

        footer, .footer {
            text-align: center;
            color: var(--muted);
            font-size: 12px;
            margin-top: 48px;
            padding: 16px 0;
            border-top: 1px solid var(--border);
        }

        .footer-note {
            margin-top: 0.5rem;
            font-size: 12px;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .dashboard {
                padding: 1rem;
            }

            .header-content {
                flex-direction: column;
                gap: 1.5rem;
            }

            .header-stats {
                width: 100%;
                justify-content: space-around;
            }

            .dev-grid {
                grid-template-columns: 1fr;
            }

            .highlights-grid {
                grid-template-columns: 1fr;
            }

            .metrics-grid {
                grid-template-columns: 1fr;
            }
        }
        """

    def _generate_markdown(self, metrics: BoardMetrics, options: ReportOptions) -> str:
        """Generate Markdown report"""
        lines = []

        # Header
        lines.append(f"# Developer Performance Report: {metrics.board}")
        lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
        lines.append(f"**Iteration:** {metrics.iteration_path.split('\\')[-1]}")
        lines.append(f"**Period:** Last 7 days\n")

        # Team summary
        week_total = sum(dev.performance.user_stories.completed_this_iteration for dev in metrics.developers)
        blocked_total = sum(dev.performance.user_stories.blocked for dev in metrics.developers)

        lines.append("## Team Summary")
        lines.append(f"- **Stories Completed This Week:** {week_total}")
        lines.append(f"- **Currently Blocked:** {blocked_total}")
        lines.append(f"- **Active Developers:** {len(metrics.developers)}\n")

        # Developer metrics
        lines.append("## Individual Performance")
        for dev in metrics.developers:
            perf = dev.performance
            completion_pct = int((perf.story_points.completed / perf.story_points.committed) * 100) if perf.story_points.committed > 0 else 0

            lines.append(f"\n### {dev.developer.display_name}")
            lines.append(f"**Completion:** {completion_pct}% ({int(perf.story_points.completed)}/{int(perf.story_points.committed)} pts)")
            lines.append(f"- **This Week:** {perf.user_stories.completed_this_iteration} stories")
            lines.append(f"- **In Progress:** {perf.user_stories.open} items")

            if perf.user_stories.blocked > 0:
                lines.append(f"- ** ️ Blocked:** {perf.user_stories.blocked} items")
            if perf.user_stories.past_due > 0:
                lines.append(f"- ** Past Due:** {perf.user_stories.past_due} items")

            if options.include_achievements and dev.impact.key_achievements:
                lines.append("\n**Key Achievements:**")
                for achievement in dev.impact.key_achievements[:3]:
                    lines.append(f"- {achievement.title}")

        lines.append("\n---")
        lines.append(f"*ADO Metrics Tool v1.0.0 | {'DRY RUN MODE' if options.dry_run else 'Production Mode'}*")

        return '\n'.join(lines)

    def _generate_json(self, metrics: BoardMetrics, options: ReportOptions) -> str:
        """Generate JSON report"""
        # Convert metrics to dictionary
        data = {
            'board': metrics.board,
            'area_path': metrics.area_path,
            'iteration_path': metrics.iteration_path,
            'generated_at': datetime.now().isoformat(),
            'period': 'last_7_days',
            'team_summary': {
                'stories_completed_this_week': sum(dev.performance.user_stories.completed_this_iteration for dev in metrics.developers),
                'items_blocked': sum(dev.performance.user_stories.blocked for dev in metrics.developers),
                'items_past_due': sum(dev.performance.user_stories.past_due for dev in metrics.developers),
                'active_developers': len(metrics.developers)
            },
            'developers': []
        }

        for dev in metrics.developers:
            dev_data = {
                'name': dev.developer.display_name,
                'email': dev.developer.unique_name,
                'performance': {
                    'stories_completed_this_week': dev.performance.user_stories.completed_this_iteration,
                    'stories_in_progress': dev.performance.user_stories.open,
                    'stories_blocked': dev.performance.user_stories.blocked,
                    'stories_past_due': dev.performance.user_stories.past_due,
                    'story_points_completed': int(dev.performance.story_points.completed),
                    'story_points_committed': int(dev.performance.story_points.committed),
                    'completion_percentage': int((dev.performance.story_points.completed / dev.performance.story_points.committed * 100)) if dev.performance.story_points.committed > 0 else 0
                }
            }

            if options.include_achievements:
                dev_data['achievements'] = [
                    {
                        'title': a.title,
                        'impact': a.impact,
                        'work_item_id': a.work_item_id
                    }
                    for a in dev.impact.key_achievements[:3]
                ]

            data['developers'].append(dev_data)

        return json.dumps(data, indent=2, default=str)