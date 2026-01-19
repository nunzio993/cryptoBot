"""
User Logs API endpoint - reads per-user log files
"""
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, Query
import os

from models import User
from api.deps import get_current_user

router = APIRouter()


def get_user_log_path(user_id: int) -> Path:
    """Get the log file path for a user"""
    if os.path.exists("/app/logs"):
        return Path(f"/app/logs/user_{user_id}.log")
    else:
        # Fallback for local development
        PROJECT_ROOT = Path(__file__).parent.parent.parent
        return PROJECT_ROOT / "logs" / f"user_{user_id}.log"


@router.get("", response_model=List[str])
async def get_logs(
    lines: int = Query(100, ge=1, le=500, description="Number of lines to return"),
    current_user: User = Depends(get_current_user)
):
    """
    Get the current user's activity log.
    Returns the last N lines (default 100, max 500), most recent first.
    """
    log_path = get_user_log_path(current_user.id)
    
    if not log_path.exists():
        return ["No activity logged yet"]
    
    try:
        all_lines = log_path.read_text(encoding='utf-8').splitlines()
        # Return most recent first
        recent_lines = all_lines[-lines:]
        recent_lines.reverse()
        return recent_lines
    except Exception as e:
        return [f"Error reading logs: {str(e)}"]
