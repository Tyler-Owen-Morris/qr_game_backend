from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import Hunt, HuntStep, PlayerHuntProgress, Player, QRCode
from schemas import HuntResponse, HuntScanRequest, HuntScanResponse
from auth.utils import get_current_user
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/{hunt_id}", response_model=HuntResponse)
async def get_hunt(hunt_id: str, current_user: Player = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    print("hunt_id:",hunt_id)
    hunt = await db.get(Hunt, hunt_id)
    if not hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")
    
    progress = await db.scalar(select(PlayerHuntProgress).where(
        PlayerHuntProgress.player_id == current_user.id,
        PlayerHuntProgress.hunt_id == hunt_id
    ))
    
    step_num = progress.current_step if progress else 0
    
    steps = await db.execute(select(HuntStep).where(HuntStep.hunt_id == hunt_id).order_by(HuntStep.order))
    steps_list = steps.scalars().all()
    current_step = steps_list[step_num] if step_num < len(steps_list) else None
    
    return {
        "id": str(hunt.id),
        "name": hunt.name,
        "description": hunt.description,
        "steps": len(steps_list),
        "current_step": {
            "latitude": current_step.latitude,
            "longitude": current_step.longitude,
            "hint": current_step.hint
        } if current_step else None
    }

@router.post("/scan", response_model=HuntScanResponse)
async def scan_hunt_qr(
    request: HuntScanRequest,
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    progress = await db.scalar(select(PlayerHuntProgress).where(
        PlayerHuntProgress.player_id == current_user.id,
        PlayerHuntProgress.hunt_id == request.hunt_id
    ))
    if not progress:
        progress = PlayerHuntProgress(player_id=current_user.id, hunt_id=request.hunt_id)
        db.add(progress)
    
    steps = await db.execute(select(HuntStep).where(HuntStep.hunt_id == request.hunt_id).order_by(HuntStep.order))
    steps_list = steps.scalars().all()
    if progress.current_step >= len(steps_list):
        raise HTTPException(status_code=400, detail="Hunt already completed")
    
    current_step = steps_list[progress.current_step]
    qr_code = await db.get(QRCode, current_step.qr_code_id)
    print("code expected:", qr_code)
    if qr_code.code != request.qr_code:
        raise HTTPException(status_code=400, detail="Wrong QR code")
    
    from utils.location import calculate_distance
    distance = calculate_distance(request.latitude, request.longitude, current_step.latitude, current_step.longitude)
    if distance > 50:
        raise HTTPException(status_code=400, detail=f"Too far: {distance:.2f}m")
    
    progress.current_step += 1
    progress.last_attempt_at = datetime.utcnow()
    
    if progress.current_step == len(steps_list):
        progress.completed_at = datetime.utcnow()
        reward = 50 if not progress.completed_at else 5  # Full reward first time, 5 after
        current_user.score = (current_user.score or 0) + reward
        await db.commit()
        return {"status": "completed", "reward": reward}
    
    next_step = steps_list[progress.current_step]
    await db.commit()
    return {
        "status": "success",
        "next_step": {"latitude": next_step.latitude, "longitude": next_step.longitude, "hint": next_step.hint}
    }