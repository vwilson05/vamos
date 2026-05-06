"""
CLI commands for ADO metrics functionality
"""

import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

import yaml

from .config import Config
from .ado import ADOClient
from .metrics import (
    ADOTeamContext,
    ADOBoardMetricsCollector,
    ReportGenerator,
    ReportOptions
)

log = logging.getLogger(__name__)


def load_metrics_config() -> Dict[str, Any]:
    """Load metrics configuration from .ado-metrics.yml"""
    config_path = Path(".ado-metrics.yml")
    default_config = {
        "metrics": {
            "always_dry_run": True,
            "require_confirmation": True
        },
        "boards": [],
        "notifications": {
            "enabled": False
        }
    }

    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                return yaml_config or default_config
        except Exception as e:
            log.warning(f"Could not load config file: {e}")

    return default_config


def load_allowed_developers() -> List[str]:
    """Load allowed developers from developers.yml"""
    developers_path = Path("developers.yml")
    if developers_path.exists():
        try:
            with open(developers_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data.get('developers', [])
        except Exception as e:
            log.warning(f"Could not load developers file: {e}")
    return []


def get_board_context(args, config: Config) -> ADOTeamContext:
    """Get board context from args or configuration"""
    metrics_config = load_metrics_config()

    # Get area and iteration paths
    area_path = args.area_path or os.getenv('METRICS_AREA_PATH')
    iteration_path = args.iteration_path or os.getenv('METRICS_ITERATION_PATH')

    # If board name is provided, look it up in config
    if hasattr(args, 'board') and args.board:
        for board in metrics_config.get('boards', []):
            if board['name'] == args.board:
                area_path = board['area_path']
                iteration_path = board['iteration_path']
                break
        else:
            log.warning(f"Board '{args.board}' not found in configuration")

    if not area_path or not iteration_path:
        print(" Error: Area path and iteration path are required")
        print("\nSpecify them via:")
        print("  --area-path and --iteration-path flags")
        print("  --board flag (if configured in .ado-metrics.yml)")
        print("  METRICS_AREA_PATH and METRICS_ITERATION_PATH environment variables")
        sys.exit(1)

    return ADOTeamContext(
        area_path=area_path,
        iteration_path=iteration_path,
        board=args.board if hasattr(args, 'board') else None,
        project=config.ado_project
    )


def cmd_metrics_generate(args, config: Config):
    """Generate metrics report (DRY RUN by default)"""
    context = get_board_context(args, config)
    metrics_config = load_metrics_config()

    # Safety check - default to dry run
    dry_run = not args.no_dry_run if hasattr(args, 'no_dry_run') else True

    # Check if sending notifications
    send_notifications = hasattr(args, 'send') and args.send

    if send_notifications and not dry_run:
        print(" ️  WARNING: You are about to send notifications!")
        print(f"   Channel: {args.send}")
        print(f"   Area: {context.area_path}")
        print(f"   Iteration: {context.iteration_path}")
        print("\nType 'yes' to confirm, anything else to cancel: ", end='')
        confirmation = input().strip().lower()

        if confirmation != 'yes':
            print(" Action cancelled")
            return

    # Set default output path with date if not provided
    if not args.output:
        from datetime import datetime
        date_str = datetime.now().strftime('%Y-%m-%d')
        board_name = (context.board or 'metrics').replace(' ', '_').lower()
        args.output = f"./metrics_reports/{date_str}_{board_name}_metrics.{args.format}"

    print(f"\n Generating metrics report {'(DRY RUN)' if dry_run else ''}")
    print(f"   Area Path: {context.area_path}")
    print(f"   Iteration: {context.iteration_path}")
    print(f"   Format: {args.format}")
    print(f"   Output: {args.output}\n")

    # Create ADO client
    ado_client = ADOClient(
        org_url=config.ado_org_url,
        project=config.ado_project,
        pat=config.ado_pat,
        read_only=config.ado_read_only
    )

    # Collect metrics
    collector = ADOBoardMetricsCollector(ado_client)
    allowed_developers = load_allowed_developers()
    metrics = collector.collect_board_metrics(context, allowed_developers)

    # Generate report
    generator = ReportGenerator()
    options = ReportOptions(
        area_path=context.area_path,
        iteration_path=context.iteration_path,
        format=args.format,
        output_path=args.output,
        dry_run=dry_run,
        send_notifications=send_notifications,
        include_charts=args.include_charts,
        include_achievements=args.include_achievements
    )

    result = generator.generate_report(metrics, options)

    print(" Report generated successfully!")
    print(f" Saved to: {result.local_path}")

    if dry_run:
        print("\n DRY RUN - No notifications sent")
        if send_notifications:
            print(f"   (Would have sent to {args.send})")
    elif result.notifications:
        print("\n Notifications:")
        for notification in result.notifications:
            status_icon = " " if notification.status == 'sent' else " "
            print(f"   {status_icon} {notification.channel}: {notification.message}")


def cmd_metrics_preview(args, config: Config):
    """Preview metrics in terminal (always DRY RUN)"""
    context = get_board_context(args, config)

    print("\n Previewing metrics (DRY RUN - Terminal Only)")
    print(f"   Area Path: {context.area_path}")
    print(f"   Iteration: {context.iteration_path}\n")

    # Create ADO client
    ado_client = ADOClient(
        org_url=config.ado_org_url,
        project=config.ado_project,
        pat=config.ado_pat,
        read_only=True  # Always read-only for preview
    )

    # Collect metrics
    collector = ADOBoardMetricsCollector(ado_client)
    allowed_developers = load_allowed_developers()
    metrics = collector.collect_board_metrics(context, allowed_developers)

    # Format for terminal display
    print("═" * 60)
    print(f"BOARD METRICS: {metrics.board}")
    print("═" * 60)
    print(f"\nTotal Work Items: {metrics.total_work_items}")
    print(f"Completed: {metrics.completed_work_items}")
    print(f"In Progress: {metrics.in_progress_work_items}")
    print(f"Blocked: {metrics.blocked_work_items}")

    if metrics.velocity:
        velocity_str = ', '.join(str(int(v)) for v in metrics.velocity)
        print(f"\nVelocity (last 5 sprints): {velocity_str}")

    print("\n--- DEVELOPER BREAKDOWN ---")
    for dev in metrics.developers:
        print(f"\n {dev.developer.display_name}")
        print(f"   Stories: {dev.performance.user_stories.completed_this_iteration} completed, "
              f"{dev.performance.user_stories.open} open")
        print(f"   Bugs: {dev.performance.bugs.resolved} resolved, "
              f"{dev.performance.bugs.open} open")
        print(f"   Story Points: {dev.performance.story_points.completed}/"
              f"{dev.performance.story_points.committed}")

        if dev.performance.user_stories.blocked > 0:
            print(f"   ️  Blocked: {dev.performance.user_stories.blocked} items")
        if dev.performance.user_stories.past_due > 0:
            print(f"   Past Due: {dev.performance.user_stories.past_due} items")

    print("\n" + "═" * 60)


def cmd_metrics_developer(args, config: Config):
    """Generate metrics for specific developer"""
    context = get_board_context(args, config)
    email = args.email

    print(f"\n Generating developer metrics for: {email}")
    print(f"   Area Path: {context.area_path}")
    print(f"   Iteration: {context.iteration_path}\n")

    # Create ADO client
    ado_client = ADOClient(
        org_url=config.ado_org_url,
        project=config.ado_project,
        pat=config.ado_pat,
        read_only=True
    )

    # Collect metrics
    collector = ADOBoardMetricsCollector(ado_client)
    allowed_developers = load_allowed_developers()
    metrics = collector.collect_board_metrics(context, allowed_developers)

    # Find developer metrics
    developer_metrics = None
    for dev in metrics.developers:
        if dev.developer.unique_name.lower() == email.lower():
            developer_metrics = dev
            break

    if not developer_metrics:
        print(f" ️  No metrics found for developer: {email}")
        return

    # Format output based on requested format
    if args.format == 'json':
        output = json.dumps(developer_metrics.__dict__, default=str, indent=2)
        if args.output:
            Path(args.output).write_text(output, encoding='utf-8')
            print(f" Saved to: {args.output}")
        else:
            print(output)
    else:
        # Markdown format
        report = _format_developer_report(developer_metrics)
        print(report)


def _format_developer_report(metrics) -> str:
    """Format developer report as markdown"""
    lines = []

    lines.append(f"# Developer Performance Report")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    lines.append(f"## {metrics.developer.display_name}")
    lines.append(f"{metrics.context.area_path} - {metrics.context.iteration_path}\n")

    lines.append("### Performance Metrics")
    lines.append(f" **Completed:** {metrics.performance.user_stories.completed_this_iteration} stories "
                f"({metrics.performance.story_points.completed} pts)")
    lines.append(f" **In Progress:** {metrics.performance.user_stories.open} stories")
    lines.append(f" **Bugs Fixed:** {metrics.performance.bugs.resolved}")

    if metrics.performance.user_stories.blocked > 0:
        lines.append(f" **Blocked:** {metrics.performance.user_stories.blocked} items")
    if metrics.performance.user_stories.past_due > 0:
        lines.append(f" ️ **Past Due:** {metrics.performance.user_stories.past_due} items")

    if metrics.impact.key_achievements:
        lines.append("\n### Key Achievements")
        for achievement in metrics.impact.key_achievements:
            lines.append(f"• {achievement.title} ({achievement.impact} IMPACT)")

    lines.append(f"\n### Impact Score: {metrics.impact.customer_impact_score}/100")

    return '\n'.join(lines)


def cmd_metrics_export(args, config: Config):
    """Export raw metrics data as JSON"""
    context = get_board_context(args, config)

    # Set default output path with date if not provided
    if not args.output:
        from datetime import datetime
        date_str = datetime.now().strftime('%Y-%m-%d')
        board_name = (context.board or 'metrics').replace(' ', '_').lower()
        args.output = f"./metrics_reports/{date_str}_{board_name}_data.json"

    print("\n Exporting metrics data")
    print(f"   Area Path: {context.area_path}")
    print(f"   Iteration: {context.iteration_path}")
    print(f"   Output: {args.output}\n")

    # Create ADO client
    ado_client = ADOClient(
        org_url=config.ado_org_url,
        project=config.ado_project,
        pat=config.ado_pat,
        read_only=True
    )

    # Collect metrics
    collector = ADOBoardMetricsCollector(ado_client)
    allowed_developers = load_allowed_developers()
    metrics = collector.collect_board_metrics(context, allowed_developers)

    # Save as JSON
    output_path = Path(args.output)
    output_path.write_text(
        json.dumps(metrics.__dict__, default=str, indent=2),
        encoding='utf-8'
    )
    print(f" Data exported to: {args.output}")


def cmd_metrics_boards(args, config: Config):
    """List configured boards"""
    metrics_config = load_metrics_config()

    print("\n Configured Boards:\n")

    boards = metrics_config.get('boards', [])
    if boards:
        for i, board in enumerate(boards, 1):
            default_marker = " (default)" if board['name'] == metrics_config.get('default_board') else ""
            print(f"{i}. {board['name']}{default_marker}")
            print(f"   Area: {board['area_path']}")
            print(f"   Iteration: {board['iteration_path']}")
            print()
    else:
        print("No boards configured in .ado-metrics.yml")

    # Show environment variables if set
    area_path = os.getenv('METRICS_AREA_PATH')
    iteration_path = os.getenv('METRICS_ITERATION_PATH')
    if area_path or iteration_path:
        print("Environment Variables:")
        if area_path:
            print(f"  METRICS_AREA_PATH={area_path}")
        if iteration_path:
            print(f"  METRICS_ITERATION_PATH={iteration_path}")


def add_metrics_subcommands(subparsers):
    """Add metrics subcommands to the CLI"""

    # Main metrics command
    metrics_parser = subparsers.add_parser('metrics', help='Generate and manage ADO metrics reports')
    metrics_sub = metrics_parser.add_subparsers(dest='metrics_cmd', required=True)

    # Generate command
    p_generate = metrics_sub.add_parser('generate', help='Generate metrics report (DRY RUN by default)')
    p_generate.add_argument('--area-path', help='ADO area path (e.g., "Data Platform\\Engineering")')
    p_generate.add_argument('--iteration-path', help='ADO iteration path')
    p_generate.add_argument('--board', help='Use predefined board from config')
    p_generate.add_argument('--format', choices=['html', 'json', 'markdown'], default='html',
                           help='Output format')
    p_generate.add_argument('--output', help='Output file path (default: metrics_reports/YYYY-MM-DD_metrics.html)')
    p_generate.add_argument('--include-charts', action='store_true', default=True,
                           help='Include charts in report')
    p_generate.add_argument('--include-achievements', action='store_true', default=True,
                           help='Include developer achievements')
    p_generate.add_argument('--send', help='DANGEROUS: Actually send to slack/teams (requires confirmation)')
    p_generate.add_argument('--no-dry-run', action='store_true',
                           help='DANGEROUS: Disable dry-run mode (not recommended)')
    p_generate.set_defaults(func=cmd_metrics_generate)

    # Preview command
    p_preview = metrics_sub.add_parser('preview', help='Preview metrics in terminal (always DRY RUN)')
    p_preview.add_argument('--area-path', help='ADO area path')
    p_preview.add_argument('--iteration-path', help='ADO iteration path')
    p_preview.add_argument('--board', help='Use predefined board from config')
    p_preview.set_defaults(func=cmd_metrics_preview)

    # Developer command
    p_developer = metrics_sub.add_parser('developer', help='Generate metrics for specific developer')
    p_developer.add_argument('email', help='Developer email address')
    p_developer.add_argument('--area-path', help='ADO area path')
    p_developer.add_argument('--iteration-path', help='ADO iteration path')
    p_developer.add_argument('--format', choices=['markdown', 'json'], default='markdown',
                            help='Output format')
    p_developer.add_argument('--output', help='Output file path')
    p_developer.add_argument('--include-achievements', action='store_true', default=True)
    p_developer.set_defaults(func=cmd_metrics_developer)

    # Export command
    p_export = metrics_sub.add_parser('export', help='Export raw metrics data as JSON')
    p_export.add_argument('--area-path', help='ADO area path')
    p_export.add_argument('--iteration-path', help='ADO iteration path')
    p_export.add_argument('--board', help='Use predefined board from config')
    p_export.add_argument('--output', help='Output file path (default: metrics_reports/YYYY-MM-DD_metrics_data.json)')
    p_export.set_defaults(func=cmd_metrics_export)

    # Boards command
    p_boards = metrics_sub.add_parser('boards', help='List configured boards')
    p_boards.set_defaults(func=cmd_metrics_boards)