"""Scan routes for discovering sequencing files."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from aco.manifest import ScanResult, scan_directory_async


router = APIRouter(prefix="/scan", tags=["scan"])


class ScanRequest(BaseModel):
    """Request body for file scanning."""
    
    target_directory: str
    max_depth: int = 10
    include_hidden: bool = False


class ScanResponse(BaseModel):
    """Response from file scan."""
    
    message: str
    result: ScanResult


@router.post("", response_model=ScanResponse)
async def scan_files(request: ScanRequest) -> ScanResponse:
    """
    Scan a directory for sequencing files.
    
    Discovers FASTQ, BAM, CellRanger outputs, and other
    sequencing-related files.
    """
    try:
        result = await scan_directory_async(
            root_path=request.target_directory,
            max_depth=request.max_depth,
            include_hidden=request.include_hidden,
        )
        
        return ScanResponse(
            message=f"Scan completed. Found {result.total_files} files.",
            result=result,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"Permission denied: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {e}")


@router.get("/preview", response_model=ScanResponse)
async def preview_scan(
    target_directory: str,
    max_depth: int = 3,
) -> ScanResponse:
    """
    Quick preview scan with limited depth.
    
    Useful for getting a quick overview of what's in a directory
    without a full deep scan.
    """
    try:
        result = await scan_directory_async(
            root_path=target_directory,
            max_depth=max_depth,
            include_hidden=False,
        )
        
        return ScanResponse(
            message=f"Preview scan completed. Found {result.total_files} files.",
            result=result,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan failed: {e}")
