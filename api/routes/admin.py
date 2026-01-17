"""
Admin routes - User management for admin users only
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from models import User
from api.deps import get_db, get_current_user

router = APIRouter()


def require_admin(current_user: User = Depends(get_current_user)):
    """Dependency to check if current user is admin"""
    if current_user.username.lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: Optional[str]
    two_factor_enabled: bool
    
    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(require_admin),
    db=Depends(get_db)
):
    """List all users (admin only)"""
    users = db.query(User).order_by(User.id).all()
    return [
        UserResponse(
            id=u.id,
            username=u.username,
            email=u.email,
            created_at=u.created_at.isoformat() if u.created_at else None,
            two_factor_enabled=u.two_factor_enabled or False
        )
        for u in users
    ]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db=Depends(get_db)
):
    """Get a single user by ID (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        created_at=user.created_at.isoformat() if user.created_at else None,
        two_factor_enabled=user.two_factor_enabled or False
    )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdateRequest,
    current_user: User = Depends(require_admin),
    db=Depends(get_db)
):
    """Update user email (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if data.email:
        # Check if email is already taken by another user
        existing = db.query(User).filter(
            User.email == data.email,
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = data.email
    
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        created_at=user.created_at.isoformat() if user.created_at else None,
        two_factor_enabled=user.two_factor_enabled or False
    )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db=Depends(get_db)
):
    """Delete a user and all their data (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    db.delete(user)
    db.commit()
    
    return {"message": f"User {user.username} deleted successfully"}
