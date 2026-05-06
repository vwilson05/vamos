"""
ADO Metrics Collector - Gathers metrics from Azure DevOps
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from collections import defaultdict

from ..ado import ADOClient, WorkItem
from .types import (
    ADOTeamContext,
    BoardMetrics,
    DeveloperMetrics,
    DeveloperInfo,
    PerformanceMetrics,
    WorkItemMetrics,
    BugMetrics,
    TaskMetrics,
    StoryPointMetrics,
    ImpactMetrics,
    Achievement,
    BurndownData
)

log = logging.getLogger(__name__)


class ADOBoardMetricsCollector:
    """Collects metrics for ADO boards based on area and iteration paths"""

    def __init__(self, ado_client: ADOClient):
        self.client = ado_client
        self.project = ado_client.project

    def collect_board_metrics(self, context: ADOTeamContext, allowed_developers: List[str] = None) -> BoardMetrics:
        """Collect metrics for an entire board based on area and iteration paths"""
        log.info(f"Collecting metrics for board: {context.area_path} - {context.iteration_path}")

        # Query all work items for the board
        work_items = self._query_board_work_items(context)

        # Group work items by assignee
        developer_work_items = self._group_by_developer(work_items)

        # Calculate metrics for each developer
        developer_metrics = []
        for developer_email, items in developer_work_items.items():
            if developer_email != 'Unassigned':
                # Skip conflict/duplicate users (system-generated conflict resolution users)
                if 'oidconflict' in developer_email.lower() or 'conflict_' in developer_email.lower():
                    log.info(f"Skipping conflict user: {developer_email}")
                    continue

                # If allowed_developers is specified, check if developer's display name is in the list
                if allowed_developers:
                    display_name = self._extract_display_name(developer_email)
                    # Check for partial matches (last name or full name)
                    if not any(dev.lower() in display_name.lower() or display_name.lower() in dev.lower()
                             for dev in allowed_developers):
                        continue

                metrics = self._calculate_developer_metrics(
                    developer_email,
                    items,
                    context
                )
                developer_metrics.append(metrics)

        # Calculate board-level metrics
        velocity = self._calculate_velocity(context)
        burndown = self._calculate_burndown(context)

        return BoardMetrics(
            board=context.board or context.iteration_path,
            area_path=context.area_path,
            iteration_path=context.iteration_path,
            total_work_items=len(work_items),
            completed_work_items=len([w for w in work_items if self._is_completed(w)]),
            in_progress_work_items=len([w for w in work_items if self._is_in_progress(w)]),
            blocked_work_items=len([w for w in work_items if self._is_blocked(w)]),
            developers=developer_metrics,
            velocity=velocity,
            burndown=burndown
        )

    def _query_board_work_items(self, context: ADOTeamContext) -> List[WorkItem]:
        """Query work items for a specific board context"""
        wiql_query = f"""
        SELECT [System.Id]
        FROM WorkItems
        WHERE [System.AreaPath] UNDER '{context.area_path}'
        AND [System.IterationPath] = '{context.iteration_path}'
        AND [System.WorkItemType] IN ('User Story', 'Bug', 'Task', 'Feature')
        ORDER BY [System.CreatedDate] DESC
        """

        # Execute the WIQL query using the client's session
        url = f"{self.client.base}/wit/wiql?api-version=7.1"
        response = self.client.session.post(
            url,
            json={"query": wiql_query},
            timeout=self.client.timeout
        )
        response.raise_for_status()
        result = response.json()

        # Get the work item IDs
        work_item_ids = [int(item["id"]) for item in result.get("workItems", [])]

        if not work_item_ids:
            log.warning("No work items found for the specified context")
            return []

        # Fetch full work item details (batch get)
        work_items = self.client.get_work_items(work_item_ids)

        return work_items

    def _calculate_developer_metrics(
        self,
        developer_email: str,
        work_items: List[WorkItem],
        context: ADOTeamContext
    ) -> DeveloperMetrics:
        """Calculate metrics for a specific developer"""
        now = datetime.now()
        one_week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        # Separate work items by type
        user_stories = [w for w in work_items if w.type == 'User Story']
        bugs = [w for w in work_items if w.type == 'Bug']
        tasks = [w for w in work_items if w.type == 'Task']

        # Calculate story points - separate for this week vs active
        story_points_completed_this_week = sum(
            self._get_story_points(us) for us in user_stories
            if self._is_completed(us) and self._completed_in_period(us, one_week_ago, now)
        )
        story_points_active = sum(
            self._get_story_points(us) for us in user_stories
            if not self._is_completed(us)
        )
        # Keep total for backward compatibility but we'll use the weekly ones in display
        story_points_completed = story_points_completed_this_week
        story_points_committed = story_points_completed_this_week + story_points_active

        # Identify achievements
        achievements = self._identify_achievements(work_items)

        # Build developer metrics
        developer_info = DeveloperInfo(
            id=developer_email,
            display_name=self._extract_display_name(developer_email),
            unique_name=developer_email,
            area_path=context.area_path
        )

        performance = PerformanceMetrics(
            user_stories=WorkItemMetrics(
                open=len([us for us in user_stories if not self._is_completed(us)]),
                completed_this_iteration=len([
                    us for us in user_stories
                    if self._is_completed(us) and self._completed_in_period(us, one_week_ago, now)
                ]),
                completed_last_iteration=len([
                    us for us in user_stories
                    if self._is_completed(us) and self._completed_in_period(us, two_weeks_ago, one_week_ago)
                ]),
                blocked=len([us for us in user_stories if self._is_blocked(us)]),
                past_due=len([us for us in user_stories if self._is_past_due(us)]),
                no_target_date=len([us for us in user_stories if not self._has_target_date(us)])
            ),
            bugs=BugMetrics(
                open=len([b for b in bugs if not self._is_completed(b)]),
                resolved=len([b for b in bugs if self._is_completed(b)]),
                critical=len([b for b in bugs if self._is_critical(b)]),
                average_resolution_time=self._calculate_average_resolution_time(bugs)
            ),
            tasks=TaskMetrics(
                completed=len([t for t in tasks if self._is_completed(t)]),
                in_progress=len([t for t in tasks if self._is_in_progress(t)]),
                not_started=len([t for t in tasks if self._is_not_started(t)])
            ),
            story_points=StoryPointMetrics(
                completed=story_points_completed,
                committed=story_points_committed,
                velocity_average=self._calculate_average_velocity(developer_email, context)
            )
        )

        impact = ImpactMetrics(
            key_achievements=achievements,
            bugs_fixed=len([b for b in bugs if self._is_completed(b)]),
            features_delivered=len([us for us in user_stories if self._is_completed(us)]),
            code_reviews_completed=0,  # Would need PR data
            documentation_updated=False,  # Would need to check for doc work items
            customer_impact_score=self._calculate_customer_impact_score(work_items)
        )

        return DeveloperMetrics(
            developer=developer_info,
            context=context,
            performance=performance,
            impact=impact,
            period={
                'start_date': one_week_ago,
                'end_date': now,
                'report_generated_at': now
            }
        )

    # Helper methods for state checking
    def _is_completed(self, work_item: WorkItem) -> bool:
        """Check if work item is completed"""
        return work_item.state in ['Done', 'Closed', 'Resolved', 'Completed']

    def _is_in_progress(self, work_item: WorkItem) -> bool:
        """Check if work item is in progress"""
        return work_item.state in ['Active', 'In Progress', 'Committed']

    def _is_blocked(self, work_item: WorkItem) -> bool:
        """Check if work item is blocked"""
        return (work_item.state in ['Blocked', 'On Hold'] or
                'blocked' in [tag.lower() for tag in work_item.tags])

    def _is_not_started(self, work_item: WorkItem) -> bool:
        """Check if work item hasn't started"""
        return work_item.state in ['New', 'Proposed', 'To Do']

    def _is_past_due(self, work_item: WorkItem) -> bool:
        """Check if work item is past due"""
        target_date = work_item.raw_fields.get('Microsoft.VSTS.Scheduling.TargetDate')
        if not target_date:
            return False
        # Parse the date and remove timezone info to compare with naive datetime.now()
        target = datetime.fromisoformat(target_date.replace('Z', '+00:00')).replace(tzinfo=None)
        return target < datetime.now() and not self._is_completed(work_item)

    def _has_target_date(self, work_item: WorkItem) -> bool:
        """Check if work item has a target date"""
        return 'Microsoft.VSTS.Scheduling.TargetDate' in work_item.raw_fields

    def _is_critical(self, work_item: WorkItem) -> bool:
        """Check if bug is critical"""
        priority = work_item.priority
        severity = work_item.raw_fields.get('Microsoft.VSTS.Common.Severity')
        return priority == 1 or severity == '1 - Critical'

    def _get_story_points(self, work_item: WorkItem) -> int:
        """Get story points for a work item"""
        return work_item.raw_fields.get('Microsoft.VSTS.Scheduling.StoryPoints', 0) or 0

    def _completed_in_period(self, work_item: WorkItem, start: datetime, end: datetime) -> bool:
        """Check if work item was completed in a specific period"""
        closed_date = work_item.raw_fields.get('Microsoft.VSTS.Common.ClosedDate')
        if not closed_date:
            return False
        # Parse the date and remove timezone info to compare with naive datetimes
        closed = datetime.fromisoformat(closed_date.replace('Z', '+00:00')).replace(tzinfo=None)
        return start <= closed <= end

    def _calculate_average_resolution_time(self, bugs: List[WorkItem]) -> float:
        """Calculate average bug resolution time in days"""
        resolved_bugs = [b for b in bugs if self._is_completed(b)]
        if not resolved_bugs:
            return 0.0

        total_time = 0.0
        for bug in resolved_bugs:
            created_date = bug.raw_fields.get('System.CreatedDate')
            closed_date = bug.raw_fields.get('Microsoft.VSTS.Common.ClosedDate')
            if not created_date or not closed_date:
                continue
            # Parse and remove timezone info
            created = datetime.fromisoformat(created_date.replace('Z', '+00:00')).replace(tzinfo=None)
            closed = datetime.fromisoformat(closed_date.replace('Z', '+00:00')).replace(tzinfo=None)
            total_time += (closed - created).total_seconds()

        return total_time / len(resolved_bugs) / 86400 if resolved_bugs else 0.0  # Convert to days

    def _identify_achievements(self, work_items: List[WorkItem]) -> List[Achievement]:
        """Identify key achievements from work items completed in the last week"""
        achievements = []
        now = datetime.now()
        one_week_ago = now - timedelta(days=7)

        for item in work_items:
            if self._is_completed(item):
                closed_date = item.raw_fields.get('Microsoft.VSTS.Common.ClosedDate')
                if closed_date:
                    # Parse and remove timezone info
                    completed_date = datetime.fromisoformat(closed_date.replace('Z', '+00:00')).replace(tzinfo=None)
                    # Only include if completed in the last week
                    if one_week_ago <= completed_date <= now:
                        achievements.append(Achievement(
                            title=item.title,
                            description=f"Completed {item.type}",
                            impact=self._get_impact_level(item),
                            work_item_id=item.id,
                            completed_date=completed_date
                        ))
        # Sort by impact and return top 5
        achievements.sort(key=lambda x: (0 if x.impact == 'HIGH' else 1 if x.impact == 'MEDIUM' else 2, x.completed_date), reverse=True)
        return achievements[:5]  # Top 5 achievements from this week

    def _has_high_impact(self, work_item: WorkItem) -> bool:
        """Check if work item has high impact"""
        tags_lower = [tag.lower() for tag in work_item.tags]
        return ('high-impact' in tags_lower or
                'customer' in tags_lower or
                work_item.priority == 1)

    def _get_impact_level(self, work_item: WorkItem) -> str:
        """Get impact level for work item"""
        if work_item.priority == 1:
            return 'HIGH'
        elif work_item.priority == 2:
            return 'MEDIUM'
        return 'LOW'

    def _calculate_customer_impact_score(self, work_items: List[WorkItem]) -> int:
        """Calculate customer impact score"""
        customer_items = [
            w for w in work_items
            if 'customer' in [tag.lower() for tag in w.tags] and self._is_completed(w)
        ]
        return len(customer_items) * 10

    def _extract_display_name(self, email: str) -> str:
        """Extract display name from email"""
        name = email.split('@')[0]
        return ' '.join(word.capitalize() for word in name.replace('.', ' ').split())

    def _group_by_developer(self, work_items: List[WorkItem]) -> Dict[str, List[WorkItem]]:
        """Group work items by developer"""
        grouped = defaultdict(list)
        for item in work_items:
            assignee = item.assigned_to or 'Unassigned'
            grouped[assignee].append(item)
        return dict(grouped)

    def _calculate_velocity(self, context: ADOTeamContext) -> List[float]:
        """Calculate velocity over last N iterations"""
        # Placeholder - would need to query historical data
        return [28.0, 32.0, 35.0, 30.0, 33.0]

    def _calculate_average_velocity(self, developer_email: str, context: ADOTeamContext) -> float:
        """Calculate developer's average velocity"""
        # Placeholder - would need to query historical data
        return 30.0

    def _calculate_burndown(self, context: ADOTeamContext) -> BurndownData:
        """Calculate burndown data"""
        # Placeholder - would need to query iteration data
        now = datetime.now()
        dates = [now - timedelta(days=i) for i in range(9, -1, -1)]

        return BurndownData(
            ideal_burndown=[100, 90, 80, 70, 60, 50, 40, 30, 20, 10],
            actual_burndown=[100, 95, 85, 78, 65, 58, 45, 38, 25, 15],
            dates=dates,
            scope_changes=[]
        )