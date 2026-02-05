"""FastAPI application for aco API."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from aco.api.routes import (
    chat_router,
    intake_router,
    manifest_router,
    notebooks_router,
    reports_router,
    runs_router,
    scan_router,
    scripts_router,
    understanding_router,
)
from aco.api.routes.chat import set_stores as set_chat_stores
from aco.api.routes.intake import set_store as set_intake_store
from aco.api.routes.manifest import set_store as set_manifest_store
from aco.api.routes.notebooks import set_stores as set_notebooks_stores
from aco.api.routes.reports import set_stores as set_reports_stores
from aco.api.routes.runs import set_stores as set_runs_stores
from aco.api.routes.scripts import set_stores as set_scripts_stores
from aco.api.routes.understanding import set_stores as set_understanding_stores
from aco.engine import UnderstandingStore
from aco.manifest import ManifestStore


# Default storage directory
DEFAULT_STORAGE_DIR = Path.home() / ".aco" / "data"

# Frontend build directory - check multiple locations
def get_frontend_dir() -> Path | None:
    """Find the frontend dist directory."""
    # Check in package (installed mode)
    pkg_static = Path(__file__).parent.parent / "static"
    if pkg_static.exists() and (pkg_static / "index.html").exists():
        return pkg_static
    
    # Check relative to repo (development mode)
    repo_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if repo_dist.exists() and (repo_dist / "index.html").exists():
        return repo_dist
    
    return None


FRONTEND_DIR = get_frontend_dir()


def get_storage_dir() -> Path:
    """Get the storage directory from environment or default."""
    env_dir = os.getenv("ACO_STORAGE_DIR")
    if env_dir:
        return Path(env_dir)
    return DEFAULT_STORAGE_DIR


def get_working_dir() -> Path:
    """Get the working directory (where aco init was run)."""
    env_dir = os.getenv("ACO_WORKING_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.cwd()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    storage_dir = get_storage_dir()
    storage_dir.mkdir(parents=True, exist_ok=True)
    
    working_dir = get_working_dir()
    
    # Initialize stores
    manifest_store = ManifestStore(storage_dir / "manifests")
    understanding_store = UnderstandingStore(str(storage_dir / "understandings"))
    
    # Set stores on routers
    set_chat_stores(manifest_store, understanding_store)
    set_intake_store(manifest_store)
    set_manifest_store(manifest_store)
    set_notebooks_stores(manifest_store, understanding_store)
    set_reports_stores(manifest_store, understanding_store)
    set_runs_stores(manifest_store, understanding_store)
    set_scripts_stores(manifest_store, understanding_store)
    set_understanding_stores(manifest_store, understanding_store)
    
    # Store references on app state for access elsewhere
    app.state.manifest_store = manifest_store
    app.state.understanding_store = understanding_store
    app.state.storage_dir = storage_dir
    app.state.working_dir = working_dir
    
    print(f"aco API started. Storage: {storage_dir}, Working dir: {working_dir}")

    # If launched from CLI, print the "Server Ready" message now that we are actually ready
    cli_url = os.getenv("ACO_CLI_URL")
    if cli_url:
        from rich.console import Console
        from rich.panel import Panel
        
        console = Console()
        console.print()
        console.print(
            Panel(
                f"[bold green]Starting aco server...[/bold green]\n\n"
                f"[link={cli_url}]{cli_url}[/link]\n\n"
                f"[dim]Press Ctrl+C to stop the server[/dim]",
                title="[green]Server Ready[/green]",
                border_style="green",
            )
        )
        console.print()
    
    yield
    
    # Shutdown
    print("aco API shutting down.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="aco - Agentic Sequencing Quality Control",
        description="API for automated sequencing quality control with LLM-driven understanding",
        version="0.1.0",
        lifespan=lifespan,
    )
    
    # Configure CORS for frontend dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server
            "http://localhost:3000",  # Alternative dev server
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routers
    app.include_router(chat_router)
    app.include_router(intake_router)
    app.include_router(scan_router)
    app.include_router(manifest_router)
    app.include_router(notebooks_router)
    app.include_router(reports_router)
    app.include_router(runs_router)
    app.include_router(scripts_router)
    app.include_router(understanding_router)
    
    @app.get("/api/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy"}
    
    @app.get("/api/config")
    async def config(reveal_key: bool = False):
        """Get current configuration.
        
        Args:
            reveal_key: If true, return the full API key (for display in settings)
        """
        import os
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
        
        # Mask the key by default, showing only first 4 and last 4 chars
        if api_key and not reveal_key:
            if len(api_key) > 12:
                masked_key = api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]
            else:
                masked_key = "*" * len(api_key)
        else:
            masked_key = api_key if reveal_key else ""
        
        return {
            "working_dir": str(get_working_dir()),
            "storage_dir": str(get_storage_dir()),
            "has_api_key": bool(api_key),
            "api_key_masked": masked_key if api_key else None,
            "api_key": api_key if reveal_key and api_key else None,
        }
    
    # Serve frontend static files if available
    if FRONTEND_DIR.exists():
        # Mount static assets
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")
        
        @app.get("/")
        async def serve_frontend():
            """Serve the frontend application."""
            return FileResponse(FRONTEND_DIR / "index.html")
        
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            """Serve SPA for all other routes."""
            file_path = FRONTEND_DIR / full_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(FRONTEND_DIR / "index.html")
    else:
        @app.get("/")
        async def root():
            """Root endpoint with API info."""
            return {
                "name": "aco API",
                "version": "0.1.0",
                "description": "Agentic Sequencing Quality Control",
                "docs_url": "/docs",
                "note": "Frontend not built. Run 'npm run build' in frontend/ directory.",
            }
    
    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "aco.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
