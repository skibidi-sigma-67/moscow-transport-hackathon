from .api.dependencies import DashboardServiceDependency
from .api.router import dashboard_router
from .service import DashboardService

__all__ = [
    "DashboardService",
    "DashboardServiceDependency",
    "dashboard_router",
]
