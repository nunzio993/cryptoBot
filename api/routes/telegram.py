"""
Telegram API routes - manage Telegram subscriptions
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List

from models import ChatSubscription, User
from api.deps import get_db, get_current_user

router = APIRouter()


class TelegramSubscription(BaseModel):
    chat_id: str


class TelegramSubscriptionResponse(BaseModel):
    id: int
    chat_id: str
    enabled: bool

    class Config:
        from_attributes = True


@router.get("", response_model=List[TelegramSubscriptionResponse])
async def list_subscriptions(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """List all Telegram subscriptions for current user"""
    subs = db.query(ChatSubscription).filter(
        ChatSubscription.user_id == current_user.id
    ).all()
    return subs


@router.post("", response_model=TelegramSubscriptionResponse)
async def add_subscription(
    data: TelegramSubscription,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Add a Telegram chat ID for notifications"""
    # Check if already exists
    existing = db.query(ChatSubscription).filter(
        ChatSubscription.user_id == current_user.id,
        ChatSubscription.chat_id == data.chat_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Subscription already exists")
    
    sub = ChatSubscription(
        user_id=current_user.id,
        chat_id=data.chat_id,
        enabled=True
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.delete("/{sub_id}")
async def delete_subscription(
    sub_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Remove a Telegram subscription"""
    sub = db.query(ChatSubscription).filter(
        ChatSubscription.id == sub_id,
        ChatSubscription.user_id == current_user.id
    ).first()
    
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    db.delete(sub)
    db.commit()
    return {"message": "Subscription deleted"}


@router.post("/{sub_id}/toggle")
async def toggle_subscription(
    sub_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Enable/disable a Telegram subscription"""
    sub = db.query(ChatSubscription).filter(
        ChatSubscription.id == sub_id,
        ChatSubscription.user_id == current_user.id
    ).first()
    
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    sub.enabled = not sub.enabled
    db.commit()
    return {"enabled": sub.enabled}
