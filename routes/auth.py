from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import timedelta
from database import get_db
from models import Player
from schemas import PlayerCreate, Token
from utils.security import get_password_hash
from auth import authenticate_user, create_access_token, get_current_user
from config import settings

router = APIRouter()

@router.post("/register", response_model=Token)
async def register_user(
    user_data: PlayerCreate,
    db: AsyncSession = Depends(get_db)
):
    # Check if username exists
    result = await db.execute(
        select(Player).filter(Player.username == user_data.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )

    # Check if email exists
    result = await db.execute(
        select(Player).filter(Player.email == user_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    db_user = Player(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password
    )

    db.add(db_user)
    await db.commit()

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_data.username},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify old password
    if not await authenticate_user(db, current_user.username, old_password):
        raise HTTPException(
            status_code=400,
            detail="Incorrect password"
        )

    # Update password
    current_user.password_hash = get_password_hash(new_password)
    db.add(current_user)
    await db.commit()

    return {"message": "Password updated successfully"}