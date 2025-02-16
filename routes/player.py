from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from database import get_db
from models import Player, ScanHistory
from schemas import PlayerResponse, ScanHistoryResponse
from auth import get_current_user

router = APIRouter()

@router.get("/me", response_model=PlayerResponse)
async def get_current_player_profile(
    current_user: Player = Depends(get_current_user)
):
    return current_user

@router.get("/stats")
async def get_player_stats(
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Get total scans
    total_scans = await db.execute(
        select(ScanHistory).filter(ScanHistory.player_id == current_user.id)
    )
    total_scans = len(total_scans.scalars().all())
    
    return {
        "score": current_user.score,
        "level": current_user.level,
        "total_scans": total_scans
    }

@router.get("/history", response_model=List[ScanHistoryResponse])
async def get_scan_history(
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ScanHistory)
        .filter(ScanHistory.player_id == current_user.id)
        .order_by(ScanHistory.scanned_at.desc())
    )
    history = result.scalars().all()
    return history

@router.put("/level-up")
async def level_up_player(
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Simple level up logic - could be made more complex
    required_score = current_user.level * 100
    
    if current_user.score >= required_score:
        current_user.level += 1
        db.add(current_user)
        await db.commit()
        return {"message": f"Leveled up to {current_user.level}!"}
    
    raise HTTPException(
        status_code=400,
        detail=f"Need {required_score - current_user.score} more points to level up"
    )

@router.get("/leaderboard")
async def get_leaderboard(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Player)
        .order_by(Player.score.desc())
        .limit(10)
    )
    top_players = result.scalars().all()
    
    return [{
        "username": player.username,
        "score": player.score,
        "level": player.level
    } for player in top_players]
