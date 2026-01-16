"""
Logs routes - view application logs
"""
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, Query

from models import User
from api.deps import get_current_user

router = APIRouter()

# Use absolute path that matches Docker volume mount
# Volume is ./:/app, so logs are at /app/logs/scheduler.log
import os
if os.path.exists("/app/logs"):
    LOG_PATH = Path("/app/logs/scheduler.log")
else:
    # Fallback for local development
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    LOG_PATH = PROJECT_ROOT / "logs" / "scheduler.log"


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
