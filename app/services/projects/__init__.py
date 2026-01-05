"""Projects domain services.

This module contains business logic for:
- Projects (CRUD, team management, status transitions)
- Tasks (CRUD, dependencies, progress tracking)
- Milestones (CRUD, status transitions)
- Comments (polymorphic across project/task/milestone)
- Activities (audit trail)
- Attachments (file management)
- Templates (project templates and expansion)
- Analytics (dashboard, trends, performance)
"""
from .activities import ActivityService
from .comments import CommentService
from .attachments import AttachmentService
from .milestones import MilestoneService
from .tasks import TaskService
from .projects import ProjectService
from .analytics import ProjectsAnalyticsService
from .lookups import ProjectsLookupService
from .templates import ProjectTemplateService

from .activity_types import (
    ActivityFilters,
    ActivityCreateData,
)
from .comment_types import (
    CommentCreateData,
    CommentUpdateData,
)
from .attachment_types import (
    AttachmentUploadData,
    AttachmentConfig,
)
from .milestone_types import (
    MilestoneFilters,
    MilestoneCreateData,
    MilestoneUpdateData,
    MilestoneProgress,
)
from .task_types import (
    TaskFilters,
    TaskDependencyData,
    TaskCreateData,
    TaskUpdateData,
)
from .project_types import (
    ProjectFilters,
    ProjectUserData,
    ProjectCreateData,
    ProjectUpdateData,
    ProjectTaskStats,
)
from .analytics_types import (
    AnalyticsFilters,
    DashboardData,
    DashboardStats,
    StatusDistribution,
    StatusTrendPoint,
    AssigneeTaskStats,
    TaskDistribution,
    BudgetPerformance,
    TimelinePerformance,
    TopProject,
    ProfitabilityMetrics,
    PerformanceMetrics,
    DepartmentSummary,
)
from .template_types import (
    TaskTemplateData,
    MilestoneTemplateData,
    TemplateFilters,
    TemplateCreateData,
    TemplateUpdateData,
    CreateFromTemplateData,
    TemplateExpansionResult,
)
from .errors import (
    ProjectError,
    ProjectStatusTransitionError,
    TaskDependencyError,
    MilestoneStatusError,
    AttachmentError,
)

__all__ = [
    # Services
    "ActivityService",
    "CommentService",
    "AttachmentService",
    "MilestoneService",
    "TaskService",
    "ProjectService",
    "ProjectsAnalyticsService",
    "ProjectsLookupService",
    "ProjectTemplateService",
    # Activity types
    "ActivityFilters",
    "ActivityCreateData",
    # Comment types
    "CommentCreateData",
    "CommentUpdateData",
    # Attachment types
    "AttachmentUploadData",
    "AttachmentConfig",
    # Milestone types
    "MilestoneFilters",
    "MilestoneCreateData",
    "MilestoneUpdateData",
    "MilestoneProgress",
    # Task types
    "TaskFilters",
    "TaskDependencyData",
    "TaskCreateData",
    "TaskUpdateData",
    # Project types
    "ProjectFilters",
    "ProjectUserData",
    "ProjectCreateData",
    "ProjectUpdateData",
    "ProjectTaskStats",
    # Analytics types
    "AnalyticsFilters",
    "DashboardData",
    "DashboardStats",
    "StatusDistribution",
    "StatusTrendPoint",
    "AssigneeTaskStats",
    "TaskDistribution",
    "BudgetPerformance",
    "TimelinePerformance",
    "TopProject",
    "ProfitabilityMetrics",
    "PerformanceMetrics",
    "DepartmentSummary",
    # Template types
    "TaskTemplateData",
    "MilestoneTemplateData",
    "TemplateFilters",
    "TemplateCreateData",
    "TemplateUpdateData",
    "CreateFromTemplateData",
    "TemplateExpansionResult",
    # Errors
    "ProjectError",
    "ProjectStatusTransitionError",
    "TaskDependencyError",
    "MilestoneStatusError",
    "AttachmentError",
]
