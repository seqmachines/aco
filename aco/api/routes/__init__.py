"""API route modules."""

from aco.api.routes.intake import router as intake_router
from aco.api.routes.manifest import router as manifest_router
from aco.api.routes.notebooks import router as notebooks_router
from aco.api.routes.reports import router as reports_router
from aco.api.routes.runs import router as runs_router
from aco.api.routes.scan import router as scan_router
from aco.api.routes.scripts import router as scripts_router
from aco.api.routes.understanding import router as understanding_router

__all__ = [
    "intake_router",
    "manifest_router",
    "notebooks_router",
    "reports_router",
    "runs_router",
    "scan_router",
    "scripts_router",
    "understanding_router",
]
