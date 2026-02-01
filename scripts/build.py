#!/usr/bin/env python3
"""Build script for aco - builds frontend and prepares package."""

import shutil
import subprocess
import sys
from pathlib import Path


def main():
    repo_root = Path(__file__).parent.parent
    frontend_dir = repo_root / "frontend"
    static_dir = repo_root / "aco" / "static"
    
    print("Building aco...")
    
    # Check npm is available
    if shutil.which("npm") is None:
        print("Error: npm not found. Please install Node.js.")
        sys.exit(1)
    
    # Build frontend
    print("\n1. Installing frontend dependencies...")
    subprocess.run(["npm", "install"], cwd=frontend_dir, check=True)
    
    print("\n2. Building frontend...")
    subprocess.run(["npm", "run", "build"], cwd=frontend_dir, check=True)
    
    # Copy to package
    print("\n3. Copying to package...")
    dist_dir = frontend_dir / "dist"
    
    if static_dir.exists():
        shutil.rmtree(static_dir)
    
    shutil.copytree(dist_dir, static_dir)
    
    print(f"\n✓ Frontend built and copied to {static_dir}")
    print("\nTo install the package:")
    print("  uv sync")
    print("\nOr to build a distributable:")
    print("  uv build")


if __name__ == "__main__":
    main()
