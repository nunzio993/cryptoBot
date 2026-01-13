"""
Profile routes - user profile management
"""
import secrets
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from werkzeug.security import check_password_hash, generate_password_hash

from models import User
from api.deps import get_db, get_current_user

router = APIRouter()


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str


class ProfileResponse(BaseModel):
    id: int
    username: str
    email: str
    telegram_linked: bool

    class Config:
        from_attributes = True


class TelegramCodeResponse(BaseModel):
    code: str
    bot_link: str


BOT_LINK = "https://t.me/segnali_trading_Nunzio_bot"


@router.get("", response_model=ProfileResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    return ProfileResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        telegram_linked=current_user.telegram_link_code is None  # If None, already linked
    )


@router.put("/password")
async def change_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    if not check_password_hash(current_user.password_hash, request.old_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    
    current_user.password_hash = generate_password_hash(request.new_password)
    db.commit()
    
    return {"message": "Password updated successfully"}


@router.get("/telegram-code", response_model=TelegramCodeResponse)
async def get_telegram_code(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    if not current_user.telegram_link_code:
        # Generate new code
        code = secrets.token_hex(4)
        current_user.telegram_link_code = code
        db.commit()
    
    return TelegramCodeResponse(
        code=current_user.telegram_link_code,
        bot_link=BOT_LINK
    )
