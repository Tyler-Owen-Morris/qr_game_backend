from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,func
from database import get_db
from models import Hunt, HuntStep, PlayerHuntProgress, Player, QRCode
from schemas import HuntResponse, HuntScanRequest, HuntScanResponse, ActiveHuntResponse
from auth.utils import get_current_user
from datetime import datetime, timedelta

router = APIRouter()

@router.get("/hunt/{hunt_id}", response_model=HuntResponse)
async def get_hunt(
    hunt_id: str = Path(..., regex=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"),
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
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

@router.get("/active", response_model=ActiveHuntResponse)
async def get_active_hunts(
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=50, description="Number of records to return")
):
    progress_query = select(PlayerHuntProgress).where(
        PlayerHuntProgress.player_id == current_user.id,
        PlayerHuntProgress.completed_at.is_(None),
        PlayerHuntProgress.abandoned_at.is_(None)
    ).offset(skip).limit(limit)
    
    total_query = select(func.count()).select_from(
        select(PlayerHuntProgress).where(
            PlayerHuntProgress.player_id == current_user.id,
            PlayerHuntProgress.completed_at.is_(None),
            PlayerHuntProgress.abandoned_at.is_(None)
        ).subquery()
    )
    total = (await db.execute(total_query)).scalar()
    
    progress_list = (await db.execute(progress_query)).scalars().all()
    hunts = []
    for progress in progress_list:
        hunt = await db.get(Hunt, progress.hunt_id)
        steps = await db.execute(select(HuntStep).where(HuntStep.hunt_id == hunt.id).order_by(HuntStep.order))
        steps_list = steps.scalars().all()
        current_step = steps_list[progress.current_step] if progress.current_step < len(steps_list) else None
        hunts.append({
            "id": str(hunt.id),
            "name": hunt.name,
            "description": hunt.description,
            "steps": len(steps_list),
            "current_step": {
                "latitude": current_step.latitude,
                "longitude": current_step.longitude,
                "hint": current_step.hint,
                "order": current_step.order
            } if current_step else None,
            "completed_at": progress.completed_at
        })
    
    return {
        "hunts": hunts,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.post("/start/{hunt_id}")
async def start_hunt(hunt_id: str, current_user: Player = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    hunt = await db.get(Hunt, hunt_id)
    if not hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")
    
    progress = await db.scalar(select(PlayerHuntProgress).where(
        PlayerHuntProgress.player_id == current_user.id,
        PlayerHuntProgress.hunt_id == hunt_id
    ))
    if progress:
        if progress.completed_at:
            # raise HTTPException(status_code=400, detail="Hunt already completed")
            progress.completed_at = None
            progress.current_step = 0
            progress.last_attempt_at = datetime.utcnow()
        if progress.abandoned_at:
            progress.abandoned_at = None  # Reset if previously abandoned
        db.add(progress)
    else:
        progress = PlayerHuntProgress(player_id=current_user.id, hunt_id=hunt_id, current_step=0)
        db.add(progress)
    
    await db.commit()
    return {"status": "started", "hunt_id": hunt_id}

@router.post("/abandon/{hunt_id}")
async def abandon_hunt(hunt_id: str, current_user: Player = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    progress = await db.scalar(select(PlayerHuntProgress).where(
        PlayerHuntProgress.player_id == current_user.id,
        PlayerHuntProgress.hunt_id == hunt_id
    ))
    if not progress:
        raise HTTPException(status_code=404, detail="Hunt not started")
    if progress.completed_at:
        raise HTTPException(status_code=400, detail="Hunt already completed")
    
    progress.abandoned_at = datetime.utcnow()
    await db.commit()
    return {"status": "abandoned", "hunt_id": hunt_id}