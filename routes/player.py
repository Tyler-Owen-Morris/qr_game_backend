from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from database import get_db
from models import Player, PlayerScan, QRCode
from schemas import PlayerHistory, ScanHistoryItem, Player as PlayerSchema
from auth.utils import get_current_user
from typing import List
import uuid

router = APIRouter()

# Get player history
@router.get("/my_history", response_model=PlayerHistory)
async def get_player_history(
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    print("current user:",  current_user.username)
    query = select(PlayerScan, QRCode).join(
        QRCode,
        PlayerScan.qr_code_id == QRCode.id
    ).where(PlayerScan.player_id == current_user.id)

    result = await db.execute(query)
    scans = result.all()

    scan_history = [
        ScanHistoryItem(
            qr_code=qr.code,
            scan_time=scan.scan_time,
            success=scan.success
        )
        for scan, qr in scans
    ]

    return PlayerHistory(scans=scan_history)

# Get current player profile
@router.get("/me", response_model=PlayerSchema)
async def get_current_player(
    current_user: Player = Depends(get_current_user)
):
    return current_user

# Retrieve scan history for a player (Admin/Internal Use)
@router.get("/{player_id}/history", response_model=PlayerHistory)
async def get_player_scan_history(
    player_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Player = Depends(get_current_user)
):
    if str(current_user.id) != str(player_id):
        raise HTTPException(status_code=403, detail="Not authorized to view this player's history")

    query = select(PlayerScan, QRCode).join(
        QRCode,
        PlayerScan.qr_code_id == QRCode.id
    ).where(PlayerScan.player_id == player_id)

    result = await db.execute(query)
    scans = result.all()

    scan_history = [
        ScanHistoryItem(
            qr_code=qr.code,
            scan_time=scan.scan_time,
            success=scan.success
        )
        for scan, qr in scans
    ]

    return PlayerHistory(scans=scan_history)

# Update player progress (e.g., after scanning a QR code)
@router.post("/progress/update")
async def update_progress(
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = update(Player).where(Player.id == current_user.id).values(progress=current_user.progress + 1)
    await db.execute(query)
    await db.commit()
    return {"message": "Progress updated successfully"}

# Record a new scan
@router.post("/scan")
async def record_scan(
    qr_code_id: uuid.UUID,
    success: bool,
    current_user: Player = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    qr_code = await db.get(QRCode, qr_code_id)
    if not qr_code:
        raise HTTPException(status_code=404, detail="QR code not found")

    new_scan = PlayerScan(player_id=current_user.id, qr_code_id=qr_code_id, success=success)
    db.add(new_scan)
    await db.commit()
    return {"message": "Scan recorded successfully"}
