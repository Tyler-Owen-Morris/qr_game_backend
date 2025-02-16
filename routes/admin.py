from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from database import get_db
from models import Player, QRCode, ScanHistory
from schemas import QRCodeCreate, QRCodeResponse
from auth import get_current_user

router = APIRouter()

async def verify_admin(current_user: Player = Depends(get_current_user)):
    if current_user.username != "admin":  # Simple admin check
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return current_user

@router.post("/qr-codes", response_model=QRCodeResponse)
async def create_qr_code(
    qr_code: QRCodeCreate,
    db: AsyncSession = Depends(get_db),
    _: Player = Depends(verify_admin)
):
    db_qr_code = QRCode(**qr_code.dict())
    db.add(db_qr_code)
    await db.commit()
    await db.refresh(db_qr_code)
    return db_qr_code

@router.get("/qr-codes", response_model=List[QRCodeResponse])
async def list_qr_codes(
    db: AsyncSession = Depends(get_db),
    _: Player = Depends(verify_admin)
):
    result = await db.execute(select(QRCode))
    return result.scalars().all()

@router.delete("/qr-codes/{qr_id}")
async def delete_qr_code(
    qr_id: int,
    db: AsyncSession = Depends(get_db),
    _: Player = Depends(verify_admin)
):
    result = await db.execute(
        select(QRCode).filter(QRCode.id == qr_id)
    )
    qr_code = result.scalar_one_or_none()
    
    if not qr_code:
        raise HTTPException(status_code=404, detail="QR code not found")
    
    await db.delete(qr_code)
    await db.commit()
    return {"message": "QR code deleted"}

@router.get("/players")
async def list_players(
    db: AsyncSession = Depends(get_db),
    _: Player = Depends(verify_admin)
):
    result = await db.execute(select(Player))
    players = result.scalars().all()
    
    return [{
        "id": p.id,
        "username": p.username,
        "email": p.email,
        "score": p.score,
        "level": p.level,
        "created_at": p.created_at
    } for p in players]

@router.delete("/players/{player_id}")
async def delete_player(
    player_id: int,
    db: AsyncSession = Depends(get_db),
    _: Player = Depends(verify_admin)
):
    result = await db.execute(
        select(Player).filter(Player.id == player_id)
    )
    player = result.scalar_one_or_none()
    
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    await db.delete(player)
    await db.commit()
    return {"message": "Player deleted"}

@router.get("/analytics")
async def get_analytics(
    db: AsyncSession = Depends(get_db),
    _: Player = Depends(verify_admin)
):
    # Get total players
    result = await db.execute(select(Player))
    total_players = len(result.scalars().all())
    
    # Get total QR codes
    result = await db.execute(select(QRCode))
    total_qr_codes = len(result.scalars().all())
    
    # Get total scans
    result = await db.execute(select(ScanHistory))
    total_scans = len(result.scalars().all())
    
    # Get top players
    result = await db.execute(
        select(Player)
        .order_by(Player.score.desc())
        .limit(5)
    )
    top_players = [{
        "username": p.username,
        "score": p.score
    } for p in result.scalars().all()]
    
    return {
        "total_players": total_players,
        "total_qr_codes": total_qr_codes,
        "total_scans": total_scans,
        "top_players": top_players
    }
