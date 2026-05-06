"""
Data types for ADO Metrics system
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Literal


@dataclass
class ADOTeamContext:
    """Context for ADO board/team metrics"""
    area_path: str  # e.g., "Data Platform\\Engineering"
    iteration_path: str  # e.g., "Data Platform\\Ingestion Engineering Kanban"
    board: Optional[str] = None  # Optional board name
    project: str = "Data Platform"  # ADO project name


@dataclass
class WorkItemMetrics:
    """Metrics for different work item types"""
    open: int = 0
    completed_this_iteration: int = 0
    completed_last_iteration: int = 0
    blocked: int = 0
    past_due: int = 0
    no_target_date: int = 0


@dataclass
class BugMetrics:
    """Bug-specific metrics"""
    open: int = 0
    resolved: int = 0
    critical: int = 0
    average_resolution_time: float = 0.0  # in days


@dataclass
class TaskMetrics:
    """Task-specific metrics"""
    completed: int = 0
    in_progress: int = 0
    not_started: int = 0


@dataclass
class StoryPointMetrics:
    """Story points metrics"""
    completed: int = 0
    committed: int = 0
    velocity_average: float = 0.0


@dataclass
class PerformanceMetrics:
    """Developer performance metrics"""
    user_stories: WorkItemMetrics = field(default_factory=WorkItemMetrics)
    bugs: BugMetrics = field(default_factory=BugMetrics)
    tasks: TaskMetrics = field(default_factory=TaskMetrics)
    story_points: StoryPointMetrics = field(default_factory=StoryPointMetrics)


@dataclass
class Achievement:
    """Represents a developer achievement"""
    title: str
    description: str
    impact: Literal['HIGH', 'MEDIUM', 'LOW']
    work_item_id: int
    completed_date: datetime


@dataclass
class ImpactMetrics:
    """Developer impact metrics"""
    key_achievements: List[Achievement] = field(default_factory=list)
    bugs_fixed: int = 0
    features_delivered: int = 0
    code_reviews_completed: int = 0
    documentation_updated: bool = False
    customer_impact_score: int = 0


@dataclass
class DeveloperInfo:
    """Developer information"""
    id: str
    display_name: str
    unique_name: str  # Email/unique identifier
    area_path: str


@dataclass
class DeveloperMetrics:
    """Complete developer metrics"""
    developer: DeveloperInfo
    context: ADOTeamContext
    performance: PerformanceMetrics
    impact: ImpactMetrics
    period: Dict[str, datetime]


@dataclass
class BurndownData:
    """Burndown chart data"""
    ideal_burndown: List[float]
    actual_burndown: List[float]
    dates: List[datetime]
    scope_changes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class BoardMetrics:
    """Complete board/team metrics"""
    board: str
    area_path: str
    iteration_path: str
    total_work_items: int
    completed_work_items: int
    in_progress_work_items: int
    blocked_work_items: int
    developers: List[DeveloperMetrics]
    velocity: List[float]
    burndown: BurndownData


@dataclass
class ReportOptions:
    """Options for report generation"""
    area_path: str
    iteration_path: str
    format: Literal['html', 'json', 'markdown', 'slack', 'teams'] = 'html'
    output_path: Optional[str] = None
    dry_run: bool = True
    send_notifications: bool = False
    include_charts: bool = True
    include_achievements: bool = True
    developer_filter: Optional[List[str]] = None


@dataclass
class NotificationResult:
    """Result of a notification attempt"""
    channel: str
    status: Literal['sent', 'failed', 'skipped']
    message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ReportResult:
    """Result of report generation"""
    report: Any
    local_path: str
    preview_url: Optional[str] = None
    notifications: List[NotificationResult] = field(default_factory=list)