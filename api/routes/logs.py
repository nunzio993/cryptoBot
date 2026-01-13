"""
Logs routes - view application logs
"""
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, Query

from models import User
from api.deps import get_current_user

router = APIRouter()

LOG_PATH = Path("logs") / "scheduler.log"


@router.get("", response_model=List[str])
async def get_logs(
    lines: int = Query(100, ge=1, le=1000, description="Number of lines to return"),
    current_user: User = Depends(get_current_user)
):
    if not LOG_PATH.exists():
        return [f"Log file not found: {LOG_PATH}"]
    
    try:
        all_lines = LOG_PATH.read_text().splitlines()
        return all_lines[-lines:]
    except Exception as e:
        return [f"Error reading logs: {str(e)}"]
